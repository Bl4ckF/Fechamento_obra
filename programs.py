"""Módulos web compilados dos fontes e incorporados ao Fechamento."""
from pathlib import Path
import base64
import hashlib
import re


PROGRAMS = (
    ("cadcraft", "CADCraft", "Projetos e desenho técnico"),
    ("pdfcraft", "PDFCraft", "Documentos PDF"),
    ("photocraft", "PhotoCraft", "Fotografia e edição de imagens"),
)


def _apps_root(root: Path) -> Path:
    """Somente módulos web incorporados ao Fechamento, nunca executáveis."""
    return root / "web" / "operations"


def catalog(root: Path):
    apps_root = _apps_root(root)
    result = []
    for program_id, name, description in PROGRAMS:
        module = apps_root / program_id
        result.append({
            "id": program_id,
            "name": name,
            "description": description,
            "available": (module / 'index.html').is_file() and any(module.glob('*.wasm')),
            "url": '/operations/'+program_id+'/index.html?host=parent',
            "source_available": (root.parent / program_id / 'Cargo.toml').is_file(),
        })
    return result


def normalize_document(data):
    operation=data.get('operation')
    if operation not in {item[0] for item in PROGRAMS}:
        raise ValueError('Operação inválida.')
    context=data.get('context')
    if not isinstance(context,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,160}',context):
        raise ValueError('Rascunho da obra inválido.')
    name=data.get('name')
    if not isinstance(name,str) or not name.strip() or len(name)>240 or any(c in name for c in '/\\\x00'):
        raise ValueError('Nome do documento inválido.')
    encoded=data.get('data')
    if not isinstance(encoded,str) or len(encoded)>70_000_000:
        raise ValueError('Documento maior que 50 MB.')
    try: binary=base64.b64decode(encoded,validate=True)
    except (ValueError,TypeError):raise ValueError('Documento inválido.') from None
    if not binary or len(binary)>50_000_000:raise ValueError('Use um documento de até 50 MB.')
    ident=hashlib.sha256((context+'\x00'+operation+'\x00'+name).encode()).hexdigest()
    return {'id':ident,'operation':operation,'context':context,'name':name,'data':encoded}

