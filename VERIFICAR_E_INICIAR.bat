@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
title Engelmig - Verificar e iniciar
set "ENGELMIG_LAUNCHER_SELF=%~f0"
set "ENGELMIG_LAUNCHER_HINT=%~1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
set "PYTHON_MANAGER_AUTOMATIC_INSTALL=false"
set "PYLAUNCHER_ALLOW_INSTALL="
set "ENGELMIG_BOOT=import os;from pathlib import Path;p=Path(os.environ['ENGELMIG_LAUNCHER_SELF']);source=p.read_text(encoding='utf-8');exec(compile(source.split('\n#===ENGELMIG_PYTHON===\n',1)[1],str(p),'exec'))"
set "ENGELMIG_START_EXIT=1"
echo ENGELMIG - VERIFICAR E INICIAR - REVISAO 2
echo.
echo Localizando o Python...

if not exist "%~dp0runtime\python.exe" goto TENTAR_PY
"%~dp0runtime\python.exe" -c "import sys;sys.exit(0 if sys.version_info >= (3,9) else 1)" >nul 2>&1
if errorlevel 1 goto TENTAR_PY
"%~dp0runtime\python.exe" -u -c "%ENGELMIG_BOOT%"
goto TERMINOU

:TENTAR_PY
py -3 -c "import sys;sys.exit(0 if sys.version_info >= (3,9) else 1)" >nul 2>&1
if errorlevel 1 goto TENTAR_PYTHON
py -3 -u -c "%ENGELMIG_BOOT%"
goto TERMINOU

:TENTAR_PYTHON
python -c "import sys;sys.exit(0 if sys.version_info >= (3,9) else 1)" >nul 2>&1
if errorlevel 1 goto TENTAR_PYTHON3
python -u -c "%ENGELMIG_BOOT%"
goto TERMINOU

:TENTAR_PYTHON3
python3 -c "import sys;sys.exit(0 if sys.version_info >= (3,9) else 1)" >nul 2>&1
if errorlevel 1 goto SEM_PYTHON
python3 -u -c "%ENGELMIG_BOOT%"
goto TERMINOU

:SEM_PYTHON
echo.
echo [FALHA] Python 3.9 ou superior nao encontrado.
echo Instale o Python: https://www.python.org/downloads/windows/
echo No instalador tradicional, marque Add Python to PATH.
echo Depois execute este BAT novamente. Nao sao necessarios pacotes extras.
goto FINALIZAR

:TERMINOU
set "ENGELMIG_START_EXIT=%ERRORLEVEL%"
:FINALIZAR
echo.
echo Pressione qualquer tecla para fechar esta janela.
pause >nul
endlocal & exit /b %ENGELMIG_START_EXIT%
#===ENGELMIG_PYTHON===
"""Verificador independente: identifica a pasta e executa app.py diretamente."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections import deque
from pathlib import Path

REQUIRED = (
    'app.py', 'engine.py', 'version.json', 'data/catalogos.json',
    'web/index.html', 'web/app.js', 'web/book.js', 'web/book-print.css',
)
SKIP = {'.git', '.venv', 'venv', 'node_modules', 'dados', 'data', 'web',
        '__pycache__', 'fontes', 'runtime', '$recycle.bin'}


def project_at(folder):
    return (folder / 'app.py').is_file() and (folder / 'engine.py').is_file()


def find_projects(folder):
    """Busca local limitada: pasta do BAT, pai direto e ate dois niveis abaixo."""
    folder = Path(folder).resolve()
    if (folder / 'app.py').is_file():
        return [folder]
    if project_at(folder.parent):
        return [folder.parent]
    found = []
    pending = deque([(folder, 0)])
    visited = 0
    while pending and visited < 500:
        current, depth = pending.popleft()
        visited += 1
        if project_at(current):
            found.append(current)
            continue
        if depth >= 2:
            continue
        try:
            children = sorted(current.iterdir(), key=lambda p: p.name.casefold())
        except OSError:
            continue
        for child in children:
            if child.name.casefold() in SKIP or child.is_symlink():
                continue
            try:
                if getattr(child.stat(), 'st_file_attributes', 0) & 0x400:
                    continue
                if child.is_dir():
                    pending.append((child, depth + 1))
            except OSError:
                continue
    return found


def path_from_input(value):
    text = value.strip().strip('"')
    if not text:
        return None
    path = Path(os.path.expandvars(text)).expanduser().resolve()
    return path.parent if path.is_file() else path


def choose_root(launcher, hint=''):
    if hint.strip():
        return path_from_input(hint)
    matches = find_projects(launcher.parent)
    if len(matches) == 1:
        return matches[0]
    print('[INFO] Pasta do BAT: ' + str(launcher.parent))
    if matches:
        print('Encontrei mais de uma copia do programa:')
        for number, path in enumerate(matches, 1):
            print('  {}. {}'.format(number, path))
        answer = input('Digite o numero da copia desejada, ou Enter para sair: ').strip()
        if answer.isdigit() and 1 <= int(answer) <= len(matches):
            return matches[int(answer) - 1]
        return None
    print('Nao localizei app.py e engine.py na pasta do BAT ou nas subpastas proximas.')
    print('Cole o caminho da pasta extraida do programa. Ex.: C:\\Obras\\Fechamento_Obras_Engelmig')
    return path_from_input(input('Pasta do programa (Enter para sair): '))


def check_files(root):
    missing = [name for name in REQUIRED if not (root / name).is_file()]
    if missing:
        print('[FALHA] Arquivos do programa ausentes nesta pasta:')
        for name in missing:
            print('  - ' + str(root / name))
        print('Extraia o ZIP completo. Este BAT nao precisa de INICIAR.bat nem de VERIFICAR_INSTALACOES.bat.')
        return False
    print('[OK] Arquivos principais encontrados.')
    return True


def preflight(root):
    # Importa o programa sem iniciar servidor, sincronizacao ou banco de dados.
    probe = r'''
import sys,json,sqlite3,ssl,threading,http.server,urllib.request,secrets,uuid,webbrowser,csv,hashlib,decimal,subprocess
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
db=sqlite3.connect(':memory:')
assert db.execute('select 1').fetchone()[0] == 1
db.close()
import app
app.symbol_catalog()
print(json.dumps({'version':app.VERSION,'sqlite':sqlite3.sqlite_version}))
'''
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8')
    try:
        result = subprocess.run([sys.executable, '-c', probe], cwd=str(root), env=env,
                                capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30)
    except (OSError, subprocess.TimeoutExpired) as error:
        print('[FALHA] Nao foi possivel conferir o programa: ' + str(error))
        return False
    if result.returncode:
        print('[FALHA] A pasta foi localizada, mas o programa apresentou este erro:')
        print((result.stderr or result.stdout).strip())
        print('Se faltar um arquivo, extraia novamente o ZIP completo. Se faltar sqlite3 ou ssl, repare o Python.')
        return False
    details = json.loads(result.stdout)
    print('[OK] Programa v{} e bibliotecas do Python conferidos.'.format(details['version']))
    return True


def check_writable(root):
    raw = os.environ.get('ENGELMIG_DATA_DIR')
    folder = Path(raw) if raw else root / 'dados'
    if not folder.is_absolute():
        folder = root / folder
    try:
        folder.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(dir=str(folder)) as probe:
            probe.write(b'Teste de gravacao do iniciador.')
            probe.flush()
    except OSError as error:
        print('[FALHA] Nao foi possivel gravar em {}: {}'.format(folder, error))
        return False
    print('[OK] Gravacao permitida em: ' + str(folder))
    return True


def check_git():
    git = shutil.which('git')
    if git:
        try:
            result = subprocess.run([git, '--version'], capture_output=True, text=True,
                                    encoding='utf-8', errors='replace', timeout=5)
            if result.returncode == 0:
                print('[OK] ' + result.stdout.strip())
                return
        except (OSError, subprocess.TimeoutExpired):
            pass
    print('[AVISO] Git indisponivel. O programa abre localmente; a sincronizacao precisa do Git.')


def main():
    launcher = Path(os.environ['ENGELMIG_LAUNCHER_SELF']).resolve()
    root = choose_root(launcher, os.environ.get('ENGELMIG_LAUNCHER_HINT', ''))
    if root is None:
        print('Inicializacao cancelada. Coloque este BAT ao lado de app.py ou arraste a pasta do programa sobre o BAT.')
        return 1
    if not root.is_dir():
        print('[FALHA] A pasta informada nao existe: ' + str(root))
        return 1
    print('[INFO] Pasta do programa: ' + str(root))
    print('[OK] Python {} - {}'.format(sys.version.split()[0], sys.executable))
    if not check_files(root) or not preflight(root) or not check_writable(root):
        return 1
    check_git()
    print('\n[OK] Verificacao concluida. Abrindo o Fechamento de Obras...')
    print('Mantenha esta janela aberta enquanto usa o programa.\n', flush=True)
    return subprocess.call([sys.executable, '-u', str(root / 'app.py')], cwd=str(root))


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print('\nInicializacao encerrada.')
    except Exception as error:
        print('[FALHA] ' + str(error))
        raise SystemExit(1)
