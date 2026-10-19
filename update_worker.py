"""Executado pelo BAT fora da pasta do aplicativo, depois do servidor encerrar."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import time
from zipfile import ZipFile

# O código de validação acompanha a cópia externa deste script na preparação.
def validate(archive, expected):
    with ZipFile(archive) as z:
        members = z.infolist()
        if len(members) > 15000 or sum(i.file_size for i in members) > 650 * 1024 * 1024:
            raise ValueError('ZIP muito grande.')
        for info in members:
            import re
            p = info.filename.replace('\\', '/')
            parts = p.rstrip('/').split('/')
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
                    raise ValueError('Versão do ZIP diferente da Release.')
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


def install(root, archive, expected):
    """Substitui somente arquivos do programa. Em falha restaura os modificados."""
    root = Path(root).resolve()
    if not (root / 'app.py').exists(): raise ValueError('Pasta de instalação não encontrada.')
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
    except Exception:
        for rel in reversed(replaced):
            dest = root / rel
            old = rollback / rel
            try:
                if old.exists(): shutil.copy2(old, dest)
                elif dest.exists(): dest.unlink()
            except OSError: pass
        raise
    return len(items)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    parser.add_argument('--archive', required=True)
    parser.add_argument('--version', required=True)
    parser.add_argument('--pid', type=int, required=True)
    a = parser.parse_args()
    log = Path(a.archive).parent / 'atualizacao.log'
    try:
        wait_pid(a.pid)
        count = install(a.root, a.archive, a.version)
        log.write_text(f'Atualização {a.version}: {count} arquivos instalados.\n', encoding='utf-8')
        print(f'Concluído: {count} arquivos atualizados.', flush=True)
        return 0
    except Exception as exc:
        log.write_text(f'ERRO: {type(exc).__name__}: {exc}\n', encoding='utf-8')
        print('Falha na atualização:', exc, file=sys.stderr, flush=True)
        return 1

if __name__ == '__main__': sys.exit(main())
