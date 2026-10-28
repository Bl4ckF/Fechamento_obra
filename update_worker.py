"""Executado pelo BAT fora da pasta do aplicativo, depois do servidor encerrar."""
import argparse
import hashlib
import re
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from zipfile import ZipFile

# O código de validação acompanha a cópia externa deste script na preparação.
def validate(archive, expected):
    with ZipFile(archive) as z:
        members = z.infolist()
        if len(members) > 15000 or sum(i.file_size for i in members) > 650 * 1024 * 1024:
            raise ValueError('ZIP muito grande.')
        seen = set()
        for info in members:
            normalized = info.filename.replace('\\', '/').rstrip('/').casefold()
            if normalized in seen:
                raise ValueError('Caminho duplicado dentro do ZIP.')
            seen.add(normalized)
            p = info.filename.replace('\\', '/')
            parts = p.rstrip('/').split('/')
            if any(':' in part or part.endswith((' ', '.')) or re.fullmatch(r'(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', part) for part in parts):
                raise ValueError('Caminho incompatível ou inseguro no Windows.')
            if p.startswith('/') or any(v in ('', '.', '..') for v in parts) or re.match(r'^[A-Za-z]:', p):
                raise ValueError('Caminho inseguro dentro do ZIP.')
            if ((info.external_attr >> 16) & 0o170000) == 0o120000:
                raise ValueError('Link simbólico não permitido.')
        names = set(z.namelist())
        for name in names:
            if not name.endswith('/app.py') and name != 'app.py': continue
            prefix = name[:-len('app.py')]
            if all(prefix + s in names for s in ('updates.py', 'version.json', 'INICIAR.bat')):
                meta = json.loads(z.read(prefix + 'version.json'))
                if str(meta.get('version', '')).lstrip('v') != expected:
                    raise ValueError('A versão do ZIP difere da Release.')
                return prefix
    raise ValueError('Arquivos obrigatórios ausentes do ZIP.')


SKIP_DIRS = {'.git', 'dados', 'runtime', '.venv', '__pycache__', '.vs', '.vscode', 'dist', 'build', 'backups', '.pytest_cache'}
SKIP_FILES = {'.env', '.gitignore', 'desktop.ini', 'thumbs.db'}


def allowed(rel):
    parts = rel.parts
    if not parts or any(p.lower() in SKIP_DIRS for p in parts): return False
    if any(p.startswith('.') for p in parts): return False
    if parts[-1].lower() in SKIP_FILES or parts[-1].lower().startswith('diagnostico_instalacoes_'): return False
    if any(part.lower() == 'sincronizacao' for part in parts): return False
    return True


def wait_pid(pid, timeout=100):
    if not pid or pid == os.getpid(): return
    if os.name == 'nt':
        import ctypes
        kernel = ctypes.windll.kernel32
        kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        kernel.WaitForSingleObject.restype = ctypes.c_ulong
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        SYNCHRONIZE = 0x00100000
        handle = kernel.OpenProcess(SYNCHRONIZE, False, int(pid))
        if handle:
            try:
                result = kernel.WaitForSingleObject(handle, timeout * 1000)
                if result != 0:
                    raise TimeoutError('O servidor não encerrou dentro do prazo.')
            finally:
                kernel.CloseHandle(handle)
            return
    # Para testes e ambientes sem acesso à API do Windows.
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try: os.kill(pid, 0)
        except ProcessLookupError: return
        except PermissionError: pass
        time.sleep(.25)
    raise TimeoutError('O servidor não encerrou dentro do prazo.')


def install(root, archive, expected, expected_sha256=None):
    """Substitui somente arquivos do programa. Em falha restaura os modificados."""
    root = Path(root).resolve()
    if not (root / 'app.py').exists(): raise ValueError('Pasta de instalação não encontrada.')
    if expected_sha256 is not None:
        with open(archive, 'rb') as source:
            digest = hashlib.sha256()
            for chunk in iter(lambda: source.read(1024 * 1024), b''): digest.update(chunk)
        if digest.hexdigest() != expected_sha256:
            raise ValueError('O pacote mudou depois da verificação de assinatura.')
    version_file = root / 'version.json'
    if version_file.exists():
        current = str(json.loads(version_file.read_text(encoding='utf-8'))['version'])
        if not re.fullmatch(r'\d+\.\d+\.\d+', expected) or tuple(map(int, expected.split('.'))) <= tuple(map(int, current.split('.'))):
            raise ValueError('Instalação de versão antiga ou repetida recusada.')
    prefix = validate(archive, expected)
    staging = Path(archive).parent / 'extracao'
    rollback = Path(archive).parent / 'rollback'
    staging.mkdir(exist_ok=True)
    rollback.mkdir(exist_ok=True)
    with ZipFile(archive) as z:
        items = []
        for info in z.infolist():
            if info.is_dir() or not info.filename.startswith(prefix): continue
            rel = Path(info.filename[len(prefix):])
            if not allowed(rel): continue
            if not (root / rel).resolve().is_relative_to(root):
                raise ValueError('Destino fora da instalação (link local).')
            items.append((info, rel))
        if not items: raise ValueError('O ZIP não contém arquivos para atualizar.')
        for info, rel in items:
            dst = staging / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, open(dst, 'wb') as out: shutil.copyfileobj(src, out)
    replaced = []
    try:
        # Prepara backups de cada arquivo antes de tocar na instalação.
        for _, rel in items:
            dest = root / rel
            if dest.exists():
                if not dest.is_file(): raise ValueError('Destino de arquivo ocupado por uma pasta: ' + str(rel))
                original = rollback / rel
                original.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dest, original)
        for _, rel in items:
            dest = root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            # os.replace evita cópias parciais no arquivo de destino.
            temp = dest.with_name(dest.name + '.engelmig-new')
            try:
                shutil.copy2(staging / rel, temp)
                os.replace(temp, dest)
            finally:
                if temp.exists(): temp.unlink()
            replaced.append(rel)
    except Exception as failure:
        recovery_errors = []
        for rel in reversed(replaced):
            dest = root / rel
            old = rollback / rel
            try:
                if old.exists(): shutil.copy2(old, dest)
                elif dest.exists(): dest.unlink()
            except OSError:
                recovery_errors.append(str(rel))
        if recovery_errors:
            raise RuntimeError('Falha na restauração de: ' + ', '.join(recovery_errors) + '. Backup preservado em ' + str(rollback)) from failure
        raise
    return len(items)


def restart_app(root, port):
    """Abre o servidor na mesma origem sem criar outra guia do navegador."""
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=.25):
                pass
        except OSError:
            break
        time.sleep(.2)
    else:
        raise TimeoutError('A porta do programa ainda está em uso. Feche a instância anterior e inicie novamente.')
    return subprocess.Popen([sys.executable, '-u', str(Path(root).resolve() / 'app.py'),
                             '--no-browser', '--reuse-port', '--port', str(port)],
                            cwd=str(Path(root).resolve()), env=dict(os.environ), close_fds=True,
                            creationflags=getattr(subprocess, 'CREATE_NEW_CONSOLE', 0))


def status(path, state, message, **fields):
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + '.tmp')
    temporary.write_text(json.dumps(dict(state=state, message=message, updated_at=time.time(), **fields), ensure_ascii=False), encoding='utf-8')
    os.replace(temporary, target)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    parser.add_argument('--archive', required=True)
    parser.add_argument('--version', required=True)
    parser.add_argument('--sha256')
    parser.add_argument('--pid', type=int, required=True)
    parser.add_argument('--status-path')
    parser.add_argument('--restart-port', type=int)
    a = parser.parse_args()
    log = Path(a.archive).parent / 'atualizacao.log'
    try:
        wait_pid(a.pid)
        status(a.status_path, 'installing', 'Instalando os arquivos da atualização.', version=a.version)
        count = install(a.root, a.archive, a.version, a.sha256)
        log.write_text(f'Atualização {a.version}: {count} arquivos instalados.\n', encoding='utf-8')
        print(f'Concluído: {count} arquivos atualizados.', flush=True)
        if a.restart_port:
            status(a.status_path, 'restarting', 'Atualização instalada. Reiniciando o programa.', version=a.version)
            restart_app(a.root, a.restart_port)
        status(a.status_path, 'done', 'Atualização concluída.', version=a.version, files=count)
        return 0
    except Exception as exc:
        log.write_text(f'ERRO: {type(exc).__name__}: {exc}\n', encoding='utf-8')
        print('Falha na atualização:', exc, file=sys.stderr, flush=True)
        status(a.status_path, 'error', str(exc), version=a.version)
        if a.restart_port:
            try:
                restart_app(a.root, a.restart_port)
            except Exception:
                pass
        return 1

if __name__ == '__main__': sys.exit(main())
