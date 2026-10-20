"""Gera um ZIP incremental compatível com o atualizador da versão 1.3.2.

Use sempre a mesma base completa para produzir atualizações cumulativas.
Somente biblioteca padrão; Python 3.9 ou superior.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import zipfile

REQUIRED = {'app.py', 'updates.py', 'INICIAR.bat', 'version.json'}
SKIP_DIRS = {'dados', 'runtime', '.git', '.venv', '__pycache__', 'dist',
             'build', 'backups', 'sincronizacao', 'atualizacoes'}


def program_file(name):
    parts = PurePosixPath(name).parts
    return bool(parts) and not any(p.startswith('.') or p.lower() in SKIP_DIRS for p in parts) and not (
        parts[-1].lower().startswith('diagnostico_instalacoes_') or
        parts[-1].lower() == 'atualizacao.json' or
        PurePosixPath(name).suffix.lower() in ('.pyc', '.db', '.sqlite3', '.gpkg', '.log')
    )


def version(value):
    match = re.fullmatch(r'(\d+)\.(\d+)\.(\d+)', str(value))
    if not match:
        raise ValueError('Use versões no formato X.Y.Z.')
    return tuple(map(int, match.groups()))


def build(app, base, output):
    app, base, output = Path(app).resolve(), Path(base).resolve(), Path(output).resolve()
    if output.is_relative_to(app):
        raise ValueError('Salve o pacote fora da pasta do programa.')
    with zipfile.ZipFile(base) as original:
        if original.testzip():
            raise ValueError('O ZIP da base está corrompido.')
        names = original.namelist()
        roots = [name[:-len('app.py')] for name in names if name == 'app.py' or name.endswith('/app.py')]
        prefixes = [p for p in roots if all(p + required in names for required in REQUIRED)]
        if len(prefixes) != 1:
            raise ValueError('A base deve conter uma única instalação completa do programa.')
        prefix = prefixes[0]
        if not all(prefix + name in names for name in ('data/catalogos.json', 'data/composicoes_material.json', 'web/vendor/pdfjs/pdf.min.mjs')):
            raise ValueError('Use o ZIP completo como base; um pacote incremental não contém os catálogos e dependências.')
        old = {name[len(prefix):]: original.read(name) for name in names
               if name.startswith(prefix) and not name.endswith('/') and program_file(name[len(prefix):])}
    base_version = json.loads(old['version.json'])['version']
    current = json.loads((app / 'version.json').read_text(encoding='utf-8'))['version']
    if version(base_version) < (1, 3, 2) or version(current) <= version(base_version):
        raise ValueError('Use uma base completa 1.3.2 ou superior e uma versão nova maior que a base.')
    if "VERSION='" + current + "'" not in (app / 'app.py').read_text(encoding='utf-8') or (
        'v' + current not in (app / 'web/index.html').read_text(encoding='utf-8')
    ):
        raise ValueError('Alinhe as versões de app.py, version.json e web/index.html.')
    files = {p.relative_to(app).as_posix(): p for p in sorted(app.rglob('*'))
             if p.is_file() and program_file(p.relative_to(app).as_posix())}
    missing = set(old) - set(files)
    if missing:
        raise ValueError('O instalador preserva arquivos ausentes do pacote; trate as exclusões antes de publicar: ' + ', '.join(sorted(missing)))
    changed = {name: p.read_bytes() for name, p in files.items()
               if name in REQUIRED or name not in old or p.read_bytes() != old[name]}
    if not REQUIRED.issubset(changed):
        raise ValueError('Faltam arquivos obrigatórios para o atualizador.')
    manifest = {'kind': 'incremental', 'base_version': base_version, 'version': current,
                'base_sha256': hashlib.sha256(base.read_bytes()).hexdigest(),
                'files': {name: hashlib.sha256(data).hexdigest() for name, data in sorted(changed.items())}}
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + '.tmp')
    try:
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as package:
            for name, data in sorted(changed.items()):
                package.writestr('Fechamento_Obras_Engelmig/' + name, data)
            package.writestr('Fechamento_Obras_Engelmig/ATUALIZACAO.json', json.dumps(manifest, ensure_ascii=False, indent=2))
        with zipfile.ZipFile(temporary) as package:
            if package.testzip():
                raise ValueError('Falha na verificação do pacote gerado.')
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            temporary.unlink()
    return {'path': str(output), 'base_version': base_version, 'version': current,
            'files': len(changed) + 1, 'size_bytes': output.stat().st_size,
            'sha256': hashlib.sha256(output.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', required=True, help='ZIP completo de referência; preserve sempre a mesma base.')
    parser.add_argument('--saida', required=True, help='ZIP incremental a gerar, fora da pasta do programa.')
    parser.add_argument('--app', default=str(Path(__file__).resolve().parents[1]), help='Pasta do programa atualizado.')
    args = parser.parse_args()
    try:
        print(json.dumps(build(args.app, args.base, args.saida), ensure_ascii=False, indent=2))
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        parser.exit(1, 'Não foi possível gerar a atualização: ' + str(exc) + '\n')


if __name__ == '__main__':
    main()
