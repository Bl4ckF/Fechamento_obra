"""Prepare signed release assets locally. Never uploads or executes ZIP contents."""
from contextlib import contextmanager
import base64
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from update_security import file_hash, public_blob, verify

ROOT = Path(__file__).resolve().parent
PREFIX = 'Fechamento_Obras_Engelmig/'


def inspect_package(archive, root=ROOT):
    with zipfile.ZipFile(archive) as z:
        infos = z.infolist()
        if len(infos) > 20000 or sum(i.file_size for i in infos) > 1024**3:
            raise ValueError('Pacote excede os limites de arquivos ou tamanho (1 GB expandido).')
        names = set()
        files = {}
        for i in infos:
            name = i.filename
            parts = name.rstrip('/').split('/')
            if (not name.startswith(PREFIX) or '\\' in name or any(
                p in ('', '.', '..') or p.endswith((' ', '.')) or
                re.search(r'[<>:"|?*\x00-\x1f]', p) or
                re.fullmatch(r'(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', p)
                for p in parts) or stat.S_ISLNK(i.external_attr >> 16)):
                raise ValueError('Caminho inseguro no ZIP: ' + name)
            if name.rstrip('/').casefold() in names:
                raise ValueError('Caminho duplicado no ZIP: ' + name)
            names.add(name.rstrip('/').casefold())
            if not i.is_dir():
                relative = name[len(PREFIX):]
                if any(p.lower() in ('.git', 'dados', 'runtime', '__pycache__') for p in parts) or re.search(r'(?i)(chave-privada|\.dpapi\.|\.(pem|pfx|p12|key)$)', relative):
                    raise ValueError('Pacote contém dados locais ou possível chave privada: ' + relative)
                files[relative] = i
        for name in ('version.json', 'ATUALIZACAO.json', 'security/update-public.xml'):
            if name not in files or files[name].file_size > 4*1024*1024:
                raise ValueError('Pacote sem metadados válidos: ' + name)
        meta = json.loads(z.read(files['version.json']))
        version = meta.get('version', '')
        if not isinstance(version, str) or not re.fullmatch(r'\d+\.\d+\.\d+', version):
            raise ValueError('Versão inválida no version.json.')
        manifest = json.loads(z.read(files['ATUALIZACAO.json']))
        if manifest.get('version') != version or manifest.get('kind') != 'incremental':
            raise ValueError('Manifesto incompatível com a versão ou com o formato incremental.')
        hashes = manifest.get('files')
        if not isinstance(hashes, dict) or set(hashes) != set(files) - {'ATUALIZACAO.json'}:
            raise ValueError('Lista de arquivos diferente do manifesto.')
        import hashlib
        for name, expected in hashes.items():
            digest = hashlib.sha256()
            with z.open(files[name]) as stream:
                for chunk in iter(lambda: stream.read(1024*1024), b''):
                    digest.update(chunk)
            if digest.hexdigest() != expected:
                raise ValueError('Arquivo alterado ou corrompido: ' + name)
        # A public key shipped in a ZIP never establishes trust by itself.
        trusted = (root / 'security/update-public.xml').read_bytes()
        if z.read(files['security/update-public.xml']) != trusted:
            raise ValueError('A chave pública do pacote difere da chave confiável deste kit.')
        public_blob(root / 'security/update-public.xml')
        return version


def sign(archive, version):
    from native_sign import sign_message
    digest = file_hash(archive)
    message = ('Engelmig-update-v1\n'+version+'\n'+digest+'\n').encode('utf-8')
    signature = sign_message(message, ROOT/'security/update-public.xml')
    metadata = {'algorithm': 'RSA-SHA256', 'version': version, 'sha256': digest,
                'signature': base64.b64encode(signature).decode('ascii')}
    Path(str(archive)+'.sig.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')


def validate_signature(archive, version, root=ROOT):
    metadata = json.loads(Path(str(archive)+'.sig.json').read_text(encoding='utf-8-sig'))
    digest = verify(archive, metadata, version, root)
    altered = dict(metadata)
    raw = bytearray(base64.b64decode(altered['signature']))
    raw[0] ^= 1
    altered['signature'] = base64.b64encode(raw).decode('ascii')
    for invalid in (altered, dict(metadata, version=version+'.invalid'), dict(metadata, sha256='0'*64)):
        try:
            verify(archive, invalid, version, root)
        except ValueError:
            continue
        raise ValueError('Falha no teste de rejeição de assinatura adulterada.')
    return digest


def prepare(source, output, signer=sign, validator=validate_signature, root=ROOT, expected_version=None):
    version = inspect_package(source, root)
    if expected_version is not None and version != expected_version:
        raise ValueError("A versão do ZIP mudou ou difere da versão escolhida. Nenhum pacote foi assinado.")
    output.mkdir(parents=True, exist_ok=True)
    final = output / ('v'+version)
    if final.exists():
        raise ValueError('Já existe a pasta '+str(final)+'. Preserve ou mova a pasta anterior antes de repetir.')
    # Sign only a stable copy; failed runs never create the final version folder.
    with tempfile.TemporaryDirectory(prefix='.preparando-', dir=output) as temp:
        stage = Path(temp)
        assets = stage / 'ENVIAR_NO_GITHUB'
        assets.mkdir()
        archive = assets / ('Fechamento_Obras_Engelmig_Atualizacao_v'+version.replace('.', '_')+'.zip')
        shutil.copyfile(source, archive)
        if inspect_package(archive, root) != version:
            raise ValueError('O ZIP mudou durante a preparação.')
        signer(archive, version)
        digest = validator(archive, version)
        report = {'version': version, 'sha256': digest, 'signature_valid': True,
                  'tampered_signature_rejected': True, 'wrong_version_rejected': True,
                  'wrong_hash_rejected': True, 'manifest_valid': True,
                  'windows_native_verification': True, 'windows_restart_tested': False,
                  'created_at': datetime.now(timezone.utc).isoformat()}
        (stage/'VALIDACAO_OK.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        (stage/'INSTRUCOES_GITHUB.txt').write_text(
            'Crie a Release com tag v'+version+'.\nAnexe apenas os DOIS arquivos de ENVIAR_NO_GITHUB: ZIP e .zip.sig.json.\n'
            'Não modifique o ZIP assinado. O relatório fica fora da pasta de anexos.\n'
            'Esta validação verifica integridade e assinatura; não testa instalação, reinício ou funcionamento do aplicativo.\n', encoding='utf-8')
        stage.rename(final)
    return final


@contextmanager
def package_source(source):
    with zipfile.ZipFile(source) as package:
        if PREFIX+'version.json' in package.namelist():
            yield source
            return
        inner = [i for i in package.infolist() if not i.is_dir() and i.filename.lower().endswith('.zip')]
        if len(inner) != 1 or inner[0].file_size > 1024**3:
            raise ValueError('ZIP não é uma atualização nem um kit contendo uma única atualização.')
        with tempfile.TemporaryDirectory(prefix='engelmig-kit-') as temp:
            archive = Path(temp)/'atualizacao.zip'
            with package.open(inner[0]) as src, archive.open('wb') as dst:
                shutil.copyfileobj(src, dst)
            yield archive


def package_version(source):
    # Listing reads metadata only; full integrity validation follows selection.
    with package_source(source) as archive, zipfile.ZipFile(archive) as z:
        info=z.getinfo(PREFIX+'version.json')
        if info.file_size>16384:raise ValueError('Metadados de versão muito grandes.')
        version=json.loads(z.read(info)).get('version','')
        if not isinstance(version,str) or not re.fullmatch(r'\d+\.\d+\.\d+',version):
            raise ValueError('Versão inválida dentro do ZIP.')
        return version


def normalize_version_input(value):
    match=re.fullmatch(r'\s*[vV]?\s*([0-9]{1,9})\s*[._-]\s*([0-9]{1,9})\s*[._-]\s*([0-9]{1,9})\s*',str(value))
    if not match:
        raise ValueError('Use uma versão como 1.5.0, 1_5_0 ou 1-5-0 (v opcional).')
    return '.'.join(str(int(part)) for part in match.groups())


def input_zip(root=ROOT, read_input=input):
    folder=root/'ZIPS';folder.mkdir(exist_ok=True)
    (root/'ATUALIZACOES').mkdir(exist_ok=True)
    for source in sorted(root.glob('*.zip')):
        target=folder/source.name
        if target.exists():
            print('Mantido na pasta principal (nome já existe em ZIPS): '+source.name)
            continue
        with source.open('rb') as src, target.open('xb') as dst:
            shutil.copyfileobj(src,dst)
        if file_hash(source)!=file_hash(target):
            target.unlink()
            raise ValueError('Falha ao copiar o ZIP. Original preservado.')
        source.unlink()
    candidates=sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower()=='.zip')
    available=[]
    print('\nZIPs disponíveis em ZIPS:')
    for source in candidates:
        try:version=package_version(source)
        except (ValueError,KeyError,OSError,zipfile.BadZipFile) as error:
            print('  [IGNORADO] '+source.name+' — '+str(error))
            continue
        available.append((source,version))
        print('  v'+version+' — '+source.name)
    if not available:raise ValueError('Nenhum ZIP de atualização válido encontrado na pasta ZIPS.')
    while True:
        typed=read_input('\nDigite a versão que deseja preparar (1.5.0, 1_5_0 ou 1-5-0), ou 0 para cancelar: ').strip().lower()
        if typed=='0':return None
        try:version=normalize_version_input(typed)
        except ValueError as error:
            print(str(error));continue
        matches=[item for item in available if normalize_version_input(item[1])==version]
        if not matches:
            print('Versão não encontrada. Digite uma das versões listadas.');continue
        if len(matches)==1:return matches[0]
        print('Há mais de um ZIP dessa versão. Escolha o arquivo:')
        for index,(source,_) in enumerate(matches,1):print('  '+str(index)+' - '+source.name)
        while True:
            choice=read_input('Número do arquivo (0 cancela): ').strip()
            if choice=='0':return None
            if choice.isdigit() and 1<=int(choice)<=len(matches):return matches[int(choice)-1]
            print('Número inválido.')


def prepare_input(source, output, signer=sign, validator=validate_signature, root=ROOT, expected_version=None):
    with package_source(source) as archive:
        return prepare(archive,output,signer,validator,root,expected_version)


def main():
    try:
        selection = input_zip()
        if selection is None:
            print("Operação cancelada. Nenhum pacote foi assinado.");return 0
        source,version=selection
        print("Selecionado: "+source.name+" — v"+version)
        print('Conferindo pacote, assinando e validando...', flush=True)
        final = prepare_input(source, ROOT/'ATUALIZACOES', expected_version=version)
        print('\nPRONTO: '+str(final/'ENVIAR_NO_GITHUB'))
        print('Envie somente os dois arquivos dessa pasta como anexos da Release.')
        if os.name == 'nt':
            try:
                os.startfile(str(final/'ENVIAR_NO_GITHUB'))
            except OSError:
                pass
        return 0
    except Exception as error:
        print('\nFALHA: '+str(error))
        print('Nenhuma nova pasta de versão foi liberada para publicação.')
        return 1


if __name__ == '__main__':
    sys.exit(main())
