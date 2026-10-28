"""Poda routes share the main server's host, origin and token protection."""
import io
import json
import mimetypes
import os
from pathlib import Path
import re
import threading
import uuid
from urllib.parse import unquote

ROOT=Path(__file__).resolve().parent
_LOCK=threading.RLock()
_CORE=None


def core(data_dir):
    global _CORE
    with _LOCK:
        if _CORE is None:
            try:
                from . import book_engine as module
            except ImportError:
                raise ValueError('A operação Poda precisa de Pillow e ReportLab. Execute INSTALAR_RECURSOS_PODA.bat e reinicie o programa.') from None
            module.DATA=Path(data_dir)/'poda'
            for name, file in [('UPLOADS','uploads'),('BOOKS_DB','books.sqlite3'),('CONFIG','config.json'),('DRAFT','rascunho.json'),('OS_CACHE','os_cache.json')]:
                setattr(module,name,module.DATA/file)
            module.setup();module.setup_extras()
            _CORE=module
        return _CORE


def file_response(handler, path, allowed=None):
    path=Path(path).resolve()
    if allowed is not None and not path.is_relative_to(Path(allowed).resolve()):
        return handler.send({'error':'Caminho não autorizado.'},403)
    if not path.is_file():return handler.send({'error':'Arquivo não encontrado.'},404)
    kind=mimetypes.guess_type(str(path))[0] or 'application/octet-stream'
    if path.suffix=='.js':kind='text/javascript'
    return handler.send(path.read_bytes(),kind=kind)


def get(handler, path, query, data_dir, token):
    path=unquote(path)
    if path in ('/poda','/poda/'):
        return file_response(handler,ROOT/'web/index.html')
    if path.startswith('/poda/assets/'):
        relative=path[len('/poda/assets/'):]
        if relative not in {'app.js','style.css','logo.png'}:
            return handler.send({'error':'Arquivo não encontrado.'},404)
        return file_response(handler,ROOT/'web'/relative,ROOT/'web')
    c=core(data_dir)
    route=path.removeprefix('/poda')
    if route=='/api/health':return handler.send({'ok':True,'equipment':len(c.equipment().rows),'token':token})
    if route=='/api/settings':return handler.send(c.get_settings())
    if route=='/api/draft':return handler.send(c.load_draft())
    if route=='/api/materials':return handler.send(c.materials_search(query.get('q',[''])[0]))
    if route=='/api/os/markers':return handler.send(c.marker_data())
    if route=='/api/search':return handler.send(c.search_location(query.get('q',[''])[0]))
    if route=='/api/lookup':return handler.send(c.lookup_coord(query.get('coord',[''])[0]))
    if route=='/api/books':return handler.send({'rows':c.list_books(query.get('q',[''])[0])})
    if route=='/api/os':return handler.send(c.sheet_os(query.get('refresh',['0'])[0]=='1'))
    if re.fullmatch(r'/api/books/\d+(?:/pdf|/photo/\d+/(?:antes|depois))?',route):
        parts=route.split('/');row=c.get_book(int(parts[3]))
        if row is None:return handler.send({'error':'Book não encontrado.'},404)
        if route.endswith('/pdf'):return file_response(handler,row['path'])
        if '/photo/' in route:
            try:photo=row['payload']['records'][int(parts[5])][parts[6]]
            except (KeyError,IndexError,TypeError):return handler.send({'error':'Foto não encontrada.'},404)
            # Photos saved by the engine live next to the corresponding PDF.
            return file_response(handler,photo,Path(row['path']).parent)
        return handler.send(row)
    if route.startswith('/media/'):
        local=c.local_media(path)
        if local:return file_response(handler,local,c.UPLOADS)
    return handler.send({'error':'Rota de poda não encontrada.'},404)


def post(handler, path, data_dir):
    c=core(data_dir);route=path.removeprefix('/poda')
    size=int(handler.headers.get('Content-Length','0'))
    if route=='/api/upload':
        if not 0<size<=18*1024*1024:raise ValueError('Envie uma foto com até 18 MB.')
        suffix={'image/png':'.png','image/jpeg':'.jpg','image/webp':'.webp','image/bmp':'.bmp'}.get(handler.headers.get('Content-Type','').split(';')[0])
        if suffix is None:raise ValueError('Formato de imagem não aceito.')
        from PIL import Image
        raw=handler.rfile.read(size)
        try:
            with Image.open(io.BytesIO(raw)) as im:
                if im.width*im.height>40_000_000:raise ValueError('Imagem excede 40 megapixels.')
                im.verify()
        except Exception:raise ValueError('Imagem inválida ou grande demais.') from None
        name=uuid.uuid4().hex+suffix;(c.UPLOADS/name).write_bytes(raw)
        return handler.send({'url':'/poda/media/'+name})
    if not 0<size<=2_000_000:raise ValueError('Solicitação de poda excede o limite.')
    data=json.loads(handler.rfile.read(size))
    if not isinstance(data,dict):raise ValueError('Dados de poda inválidos.')
    if route=='/api/books/generate':return handler.send(c.create_book(data))
    if re.fullmatch(r'/api/books/\d+/edit',route):return handler.send(c.update_book(int(route.split('/')[3]),data))
    if route=='/api/os/marker':return handler.send(c.mark_os(data))
    if route=='/api/os/marker_type':return handler.send(c.update_marker_type(data))
    if route=='/api/settings':return handler.send(c.set_settings(data))
    if route=='/api/draft':return handler.send(c.save_draft(data))
    if route=='/api/draft/clear':return handler.send(c.save_draft({}))
    if re.fullmatch(r'/api/books/\d+/open_folder',route):
        row=c.get_book(int(route.split('/')[3]))
        if row is None:raise ValueError('Book não encontrado.')
        folder=Path(row['path']).parent
        if not folder.is_dir():raise ValueError('Pasta não encontrada.')
        if os.name=='nt':os.startfile(str(folder))
        return handler.send({'ok':True,'folder':str(folder)})
    return handler.send({'error':'Rota de poda não encontrada.'},404)
