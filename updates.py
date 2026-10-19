"""Atualizações por GitHub Releases, sem exigir clone ou Git local.

Fluxo: consultar Release -> baixar e validar ZIP -> iniciar BAT externo ->
encerrar servidor -> aplicar com rollback -> reiniciar INICIAR.bat.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import zipfile

_notices = {}
_notice_lock = threading.Lock()
MAX_DOWNLOAD = 200 * 1024 * 1024
API_REPO = 'https://api.github.com/repos/'


def version_tuple(value):
    match = re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)', str(value).strip())
    return tuple(map(int, match.groups())) if match else (0, 0, 0)


def repo_name(settings):
    value = str(settings.get('repository', '')).strip().rstrip('/').removesuffix('.git')
    match = re.fullmatch(r'https://github\.com/([\w.-]+)/([\w.-]+)', value, re.I)
    if not match:
        raise ValueError('Informe um repositório GitHub HTTPS válido nas configurações.')
    return f'{match.group(1)}/{match.group(2)}'


def latest_release(settings):
    repo = repo_name(settings)
    url = API_REPO + repo + '/releases/latest'
    with urlopen(Request(url, headers={'User-Agent': 'Engelmig-Atualizador', 'Accept': 'application/vnd.github+json'}), timeout=20) as r:
        payload = json.loads(r.read(512 * 1024).decode('utf-8'))
    tag = str(payload.get('tag_name', '')).strip()
    if version_tuple(tag) == (0, 0, 0):
        raise ValueError('A última Release não possui tag de versão válida (ex.: v11.0.1).')
    assets = [a for a in payload.get('assets', []) if str(a.get('name', '')).lower().endswith('.zip') and a.get('browser_download_url')]
    assets.sort(key=lambda a: (not ('fechamento' in a['name'].lower() or 'engelmig' in a['name'].lower()), a['name']))
    # Uma Release sem ZIP anexado usa o ZIP oficial do código da tag.
    download = assets[0]['browser_download_url'] if assets else f'https://github.com/{repo}/archive/refs/tags/{quote(tag, safe="")}.zip'
    if urlparse(download).scheme != 'https':
        raise ValueError('URL insegura no pacote de atualização.')
    return {'remote_version': tag.lstrip('v'), 'download_url': download, 'tag': tag,
            'release_url': str(payload.get('html_url', '')), 'asset_name': assets[0]['name'] if assets else ''}


def notice(root, settings, current, force=False):
    key = (str(root), str(settings.get('repository')), str(current))
    with _notice_lock:
        cached = _notices.get(key)
        if cached and not force and time.monotonic() - cached[0] < 900:
            return dict(cached[1])
    result = {'available': False, 'can_update': False, 'current_version': current, 'checked_at': time.time(), 'mode': 'release'}
    try:
        latest = latest_release(settings)
        available = version_tuple(latest['remote_version']) > version_tuple(current)
        result.update(latest, available=available, can_update=available, key=latest['tag'])
    except HTTPError as exc:
        if exc.code == 404:
            result.update(error='O GitHub não encontrou uma Release pública publicada.',
                detail='Confira o endereço do repositório e publique uma Release estável com tag vX.Y.Z. Uma tag ou commit isolado não basta. Repositórios privados exigem autenticação, que este atualizador ainda não oferece.')
        elif exc.code in (403, 429):
            result.update(error='O GitHub limitou ou recusou a consulta de atualização.',
                detail='Aguarde e tente novamente. Se persistir, confira o acesso ao repositório e a conexão da empresa.')
        else:
            result.update(error='Não foi possível consultar a Release no GitHub.',detail=f'HTTP {exc.code}. Tente novamente mais tarde.')
    except Exception as exc:
        result.update(error='Não foi possível consultar a última Release publicada no GitHub.', detail=str(exc)[:400])
    with _notice_lock:
        _notices[key] = (time.monotonic(), result)
    return dict(result)


def check(root, settings, current=None):
    if current is None:
        current = json.loads((Path(root) / 'version.json').read_text(encoding='utf-8'))['version']
    return notice(root, settings, current, force=True)


def download_release(url, destination):
    req = Request(url, headers={'User-Agent': 'Engelmig-Atualizador', 'Accept': 'application/octet-stream'})
    received = 0
    with urlopen(req, timeout=50) as response, open(destination, 'wb') as out:
        final = response.geturl()
        if urlparse(final).scheme != 'https':
            raise ValueError('O download redirecionou para uma conexão insegura.')
        while True:
            block = response.read(1024 * 1024)
            if not block: break
            received += len(block)
            if received > MAX_DOWNLOAD:
                raise ValueError('ZIP da Release excede 200 MB.')
            out.write(block)
    if not zipfile.is_zipfile(destination):
        raise ValueError('O download não contém um arquivo ZIP válido.')


def valid_archive(archive, expected_version):
    """Compartilhado com o instalador; rejeita ZIP malicioso/incompleto."""
    with zipfile.ZipFile(archive) as z:
        members = z.infolist()
        if len(members) > 15000 or sum(i.file_size for i in members) > 650 * 1024 * 1024:
            raise ValueError('ZIP muito grande para uma atualização segura.')
        candidates = []
        for i in members:
            path = i.filename.replace('\\', '/')
            segments = path.rstrip('/').split('/')
            if path.startswith('/') or any(s in ('', '.', '..') for s in segments) or re.match(r'^[A-Za-z]:', path):
                raise ValueError('Caminho inseguro dentro da atualização.')
            if ((i.external_attr >> 16) & 0o170000) == 0o120000:
                raise ValueError('Atualização contém link simbólico não permitido.')
            if segments[-1] == 'app.py':
                candidates.append('/'.join(segments[:-1]))
        for prefix in sorted(set(candidates), key=len):
            base = prefix + '/' if prefix else ''
            required = [base + s for s in ('app.py', 'updates.py', 'INICIAR.bat', 'version.json')]
            if all(name in z.namelist() for name in required):
                meta = json.loads(z.read(base + 'version.json').decode('utf-8'))
                if version_tuple(meta.get('version')) != version_tuple(expected_version):
                    raise ValueError('A versão do pacote não corresponde à tag da Release. Atualize version.json antes de publicar.')
                return base
    raise ValueError('O ZIP não contém app.py, updates.py, INICIAR.bat e version.json na mesma pasta.')


def apply(root, settings, current):
    """Prepara atualização e aciona BAT. Caller deve desligar o servidor após responder."""
    state = check(root, settings, current)
    if state.get('error'):
        raise ValueError(state['error'] + ' ' + state.get('detail', ''))
    if not state['available']:
        return {'started': False, 'updated': False, 'message': 'O aplicativo já está na versão mais recente.'}
    root = Path(root).resolve()
    if os.name != 'nt':
        raise ValueError('A instalação automática por BAT está disponível no Windows.')
    work = Path(tempfile.mkdtemp(prefix='engelmig-update-'))
    try:
        archive = work / 'release.zip'
        download_release(state['download_url'], archive)
        valid_archive(archive, state['remote_version'])
        shutil.copy2(Path(__file__).with_name('update_worker.py'), work / 'update_worker.py')
        # BAT e worker ficam fora da pasta que será substituída.
        bat = work / 'ATUALIZAR_E_REINICIAR.bat'
        py = Path(sys.executable).resolve()
        def bat_quote(p):
            s = str(p)
            if any(ch in s for ch in ('\r', '\n', '"', '%', '!')):
                raise ValueError('Caminho contém caracteres incompatíveis com o BAT.')
            return '"' + s + '"'
        bat.write_text(
            '@echo off\nsetlocal DisableDelayedExpansion\nchcp 65001 >nul\n'
            'title Engelmig - Atualizacao automatica\n'
            'echo Aguardando o encerramento do aplicativo...\n'
            f'{bat_quote(py)} {bat_quote(work / "update_worker.py")} '
            f'--root {bat_quote(root)} --archive {bat_quote(archive)} '
            f'--version {bat_quote(state["remote_version"])} --pid {os.getpid()}\n'
            'if errorlevel 1 goto ERRO\n'
            'echo Atualizacao instalada. Abrindo o programa...\n'
            f'start "" {bat_quote(root / "INICIAR.bat")}\n'
            'exit /b 0\n:ERRO\n'
            'echo Falha ao atualizar. O programa anterior foi preservado ou restaurado.\n'
            'echo Confira o log de atualizacao nesta pasta.\n'
            'pause\nexit /b 1\n', encoding='utf-8-sig'
        )
        subprocess.Popen(['cmd.exe', '/c', str(bat)], cwd=str(work), creationflags=getattr(subprocess, 'CREATE_NEW_CONSOLE', 0), close_fds=True)
        return {'started': True, 'updated': False, 'remote_version': state['remote_version'],
                'message': 'Download concluído. Fechando o servidor; o BAT instalará a atualização e abrirá o aplicativo novamente.'}
    except Exception:
        shutil.rmtree(work, ignore_errors=True)
        raise
