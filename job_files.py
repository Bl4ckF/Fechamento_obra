"""Pastas locais de obras: versões editáveis, relatórios e fotos por ponto."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import threading

_WRITE_LOCK = threading.RLock()
import unicodedata
from urllib.parse import quote

ASSET = re.compile(r'^[a-f0-9]{64}\.(?:jpg|png|webp|pdf)$')


def safe_name(value, fallback='Sem_nome'):
    value = unicodedata.normalize('NFKC', str(value or ''))
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', value).strip(' .')[:72]
    if not value:
        value = fallback
    if value.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL', *('COM'+str(n) for n in range(1, 10)), *('LPT'+str(n) for n in range(1, 10))}:
        value = '_' + value
    return value


def relative_path(job):
    ident = str(job.get('id', ''))
    if not re.fullmatch(r'[a-f0-9]{32}', ident):
        raise ValueError('Identificador do registro inválido.')
    saved = str(job.get('saved_at') or '')
    year = saved[:4] if re.fullmatch(r'\d{4}', saved[:4]) else 'Sem_ano'
    work = str(job.get('work_order', ''))
    family = safe_name('Obra_' + work) + '_' + hashlib.sha256(work.encode('utf-8')).hexdigest()[:6]
    revision = safe_name(saved[:19].replace('T', '_').replace(':', '-'), 'Versao') + '_' + ident[:8]
    return Path('obras') / year / family / revision


def atomic(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_bytes(data if isinstance(data, bytes) else data.encode('utf-8'))
    os.replace(temporary, path)


def ensure_files(job, data_dir, web_root, book_report, materials_report, csv_report):
    with _WRITE_LOCK:
        return write_files(job, data_dir, web_root, book_report, materials_report, csv_report)


def write_files(job, data_dir, web_root, book_report, materials_report, csv_report):
    root = Path(data_dir).resolve()
    folder = root / relative_path(job)
    marker = folder / 'registro.json'
    if marker.is_file() and (folder / 'book.html').is_file() and (folder / 'fotos/index.json').is_file():
        return folder
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'fotos').mkdir(exist_ok=True)
    links, photos, missing = {}, [], []
    def asset(ref, rel):
        if not isinstance(ref, str) or not ASSET.fullmatch(ref):
            return
        source = root / 'media' / ref
        if not source.is_file():
            missing.append(ref)
            return
        dest = folder / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            shutil.copy2(source, dest)
        links.setdefault(ref, rel.as_posix())
    book = job.get('book') or {}
    for point in book.get('points', []):
        point_folder = 'Ponto_' + safe_name(point.get('number')) + '_' + safe_name(point.get('id'))[:10]
        for index, photo in enumerate(point.get('photos', []), 1):
            ref = photo.get('ref')
            if not isinstance(ref, str) or not ASSET.fullmatch(ref):
                continue
            filename = '{:02d}_{}.{}'.format(index, safe_name(photo.get('stage'), 'Foto'), ref.rsplit('.', 1)[1])
            rel = Path('fotos') / point_folder / filename
            asset(ref, rel)
            photos.append(dict(point=point.get('number'),file=rel.as_posix(),stage=photo.get('stage'),caption=photo.get('caption'),source=ref))
    pages = book.get('croqui_pages') or ([{'croqui': book.get('croqui'), 'drawing': book.get('drawing')}] if book.get('croqui') else [])
    for index, page in enumerate(pages, 1):
        picture = page.get('croqui') or {}
        ref = picture.get('ref')
        if ref:
            asset(ref, Path('croqui') / ('Pagina_{:03d}.'.format(index) + ref.rsplit('.', 1)[-1]))
        drawing = page.get('drawing') or {}
        for field in ('background_ref', 'pdf_text_background_ref', 'pdf_source_ref'):
            ref = drawing.get(field)
            if ref:
                asset(ref, Path('croqui/originais') / ref)
    atomic(folder / 'fotos/index.json', json.dumps(photos, ensure_ascii=False, indent=2))
    resources = ['book-print.css', 'book-print.js', 'assets/engelmig.png', 'assets/energisa.png', 'assets/rodape.png']
    for name in resources:
        source = Path(web_root) / name
        if source.is_file():
            target = folder / 'recursos' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    def offline(html):
        text = html.decode('utf-8') if isinstance(html, bytes) else html
        for ref, rel in links.items():
            text = text.replace('/media/' + ref, quote(rel, safe='/'))
        for name in resources:
            text = text.replace('/' + name, 'recursos/' + name)
        return text
    atomic(folder / 'book.html', offline(book_report))
    atomic(folder / 'mao_de_obra_e_materiais.html', offline(materials_report))
    atomic(folder / 'mao_de_obra_e_materiais.csv', csv_report)
    atomic(folder / 'LEIA-ME.txt', 'BOOK DA OBRA\n\nAbra book.html para visualizar e imprimir.\nAs fotos estão em fotos/, separadas por ponto.\nPara editar este book, abra o aplicativo, vá a Registros, escolha a obra e clique em Editar book. Ao salvar, uma nova versão é criada; esta versão é preservada.\n' + ('\nArquivos não encontrados na origem: ' + ', '.join(missing) if missing else ''))
    atomic(marker, json.dumps({'schema': 1, 'kind': 'book_obra_editavel', 'job': job, 'missing_assets': missing}, ensure_ascii=False, indent=2))
    return folder


def open_folder(folder):
    opener = getattr(os, 'startfile', None)
    if opener:
        opener(str(Path(folder).resolve()))
        return True
    return False
