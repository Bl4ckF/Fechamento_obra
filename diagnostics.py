"""Diagnóstico local limitado, sem conteúdo das obras nem mensagens de exceções."""
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import platform
import re
import threading
import traceback
import uuid
from datetime import datetime

_LOCK = threading.RLock()
_LOGGERS = {}


def record(data_dir, category, error=None, client=None):
    ident = uuid.uuid4().hex[:12]
    item = {'id': ident, 'at': datetime.now().astimezone().isoformat(timespec='seconds'),
            'category': category}
    if error is not None:
        item['type'] = type(error).__name__
        item['frames'] = [{'file': Path(f.filename).name, 'line': f.lineno, 'function': f.name}
                          for f in traceback.extract_tb(error.__traceback__)[-12:]]
    if client is not None:
        item.update(client)
    try:
        with _LOCK:
            folder = Path(data_dir).resolve() / 'diagnosticos'
            if folder not in _LOGGERS:
                folder.mkdir(parents=True, exist_ok=True)
                logger = logging.Logger('fechamento-diagnostics', logging.INFO)
                handler = RotatingFileHandler(folder / 'eventos.jsonl', maxBytes=1_000_000,
                                              backupCount=2, encoding='utf-8')
                handler.setFormatter(logging.Formatter('%(message)s'))
                logger.addHandler(handler)
                _LOGGERS[folder] = logger
            _LOGGERS[folder].info(json.dumps(item, ensure_ascii=False))
    except OSError:
        # A coleta nunca impede o usuário de salvar a obra ou ver o erro original.
        pass
    return ident


def client_event(data):
    category = data.get('category')
    if category not in ('javascript_error', 'unhandled_rejection'):
        raise ValueError('Categoria de diagnóstico inválida.')
    filename = str(data.get('file', ''))
    if filename and not re.fullmatch(r'[a-zA-Z0-9_.-]{1,80}\.m?js', filename):
        raise ValueError('Arquivo de diagnóstico inválido.')
    line = data.get('line', 0)
    if type(line) is not int or not 0 <= line <= 10_000_000:
        raise ValueError('Linha de diagnóstico inválida.')
    return category, {'file': filename, 'line': line}


def report(data_dir, version):
    events = []
    with _LOCK:
        folder = Path(data_dir) / 'diagnosticos'
        for suffix in ('.2', '.1', ''):
            file = folder / ('eventos.jsonl' + suffix)
            try:
                for line in file.read_text(encoding='utf-8').splitlines():
                    try:
                        events.append(json.loads(line))
                    except (ValueError, TypeError):
                        continue
            except OSError:
                continue
    return {'app': 'Fechamento de Obras Engelmig', 'version': version,
            'python': platform.python_version(), 'system': platform.system(),
            'created_at': datetime.now().astimezone().isoformat(timespec='seconds'),
            'events': events[-200:],
            'contents': 'Versão, sistema e localização das falhas. Sem obras, fotos, senhas ou tokens.'}
