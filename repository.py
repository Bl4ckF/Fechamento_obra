"""Endereços GitHub usados tanto na atualização quanto nos registros."""
import re
from urllib.parse import urlsplit


def normalize_repository(value):
    value = str(value or '').strip()
    if len(value) > 1000:
        raise ValueError('O endereço do repositório é muito longo.')
    if re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', value):
        value = 'https://github.com/' + value
    elif value.lower().startswith(('github.com/', 'www.github.com/')):
        value = 'https://' + value
    parsed = urlsplit(value)
    if (parsed.scheme.lower() != 'https' or parsed.netloc.lower() not in ('github.com', 'www.github.com')
            or parsed.username or parsed.password):
        raise ValueError('Cole o endereço do repositório, por exemplo: https://github.com/Bl4ckF/fechamento_obra.')
    parts = parsed.path.strip('/').split('/')
    if len(parts) < 2 or any(not re.fullmatch(r'[A-Za-z0-9_.-]+', p) or p in ('.', '..') for p in parts[:2]):
        raise ValueError('Informe o dono e o nome do repositório no GitHub.')
    if len(parts) > 2 and parts[2] not in ('tree', 'blob', 'releases', 'tags', 'commit', 'commits', 'issues', 'pulls', 'settings', 'actions'):
        raise ValueError('Cole o link da página inicial do repositório no GitHub.')
    name = parts[1].removesuffix('.git')
    if not name or name in ('.', '..'):
        raise ValueError('Nome do repositório inválido.')
    return 'https://github.com/' + parts[0] + '/' + name


def repository_name(value):
    return normalize_repository(value).removeprefix('https://github.com/')
