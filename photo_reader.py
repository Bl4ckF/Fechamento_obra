"""Local Timestamp photo reader. Organizes copies only after human review."""
import base64
from datetime import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import threading
import subprocess
from ocr_runtime import python_path
import unicodedata
import uuid
import zipfile
import stat
from pathlib import PurePosixPath
import geo

OCR_LOCK=threading.Lock()
ENGINE=None
MAX_BYTES=18*1024*1024


def extract_fields(text):
    text=str(text)[:20000]
    lines=[line.strip() for line in text.splitlines() if line.strip()]
    def field(labels):
        match=re.search(r'(?im)\b(?:'+labels+r')\s*[:#=\-]\s*(.+?)(?=\s+\b(?:PONTO|POSTE|OBRA|OS|LAT|LON)\s*[:#=]|$)',text)
        return match[1].strip()[:160] if match else ''
    work=field(r'OBRA|O\.?S\.?|ORDEM DE SERVI[ÇC]O')
    point=field(r'PONTO|POSTE|ESTRUTURA')
    if not point:
        match=re.search(r'(?im)^\s*(?:PONTO|POSTE)\s+(\d+[A-Z]?)\b',text)
        if match:point=match[1]
    location=field(r'LOCAL|LOCALIZA[ÇC][ÃA]O|ENDERE[ÇC]O')
    if not location:
        location=next((line[:300] for line in lines if re.match(r'(?i)^(RUA|AVENIDA|AV\.|RODOVIA|ESTRADA)\s',line)), '')
    coordinates=[]
    for line in lines+[' '.join(lines[i:i+2]) for i in range(max(0,len(lines)-1))]:
        candidate=re.sub(r'(?i)^(?:COORDENADAS?|GPS)\s*[:=]\s*','',line)
        # LAT/LONG labels from common Timestamp templates.
        candidate=re.sub(r'(?i)\bLONG\b','LON',candidate)
        # OCR can drop spaces: a six-digit easting and seven-digit northing
        # have an unambiguous split in this compact UTM form.
        compact=re.fullmatch(r'(\d{1,2})\s*([C-HJ-NP-X])\s*(\d{6})\s*(\d{7})',candidate,re.I)
        if compact:candidate=f'{compact[1]}{compact[2]} {compact[3]} {compact[4]}'
        try:
            lat,lon=geo.parse_coord(candidate)
            coord=geo.coordinate_formats(lat,lon)
            if not any(abs(lat-c['lat'])<1e-7 and abs(lon-c['lon'])<1e-7 for c in coordinates):
                coordinates.append({'lat':lat,'lon':lon,**coord})
        except ValueError:pass
    stage='Detalhe'
    if re.search(r'(?i)\bANTES\b',text) and not re.search(r'(?i)\bDEPOIS\b',text):stage='Antes'
    elif re.search(r'(?i)\bDEPOIS\b',text) and not re.search(r'(?i)\bANTES\b',text):stage='Depois'
    date=re.search(r'\b(\d{2}[/.-]\d{2}[/.-]\d{4})(?:\s+(\d{2}:\d{2}(?::\d{2})?))?',text)
    return {'work_order':work,'point':point,'location':location,'coordinate':coordinates[0]['utm'] or coordinates[0]['decimal'] if len(coordinates)==1 else '',
            'coordinate_candidates':coordinates,'stage':stage,'timestamp':date[0] if date else ''}


def exif_info(image):
    out={}
    try:
        exif=image.getexif();out['timestamp']=str(exif.get(36867) or exif.get(306) or '')
        gps=exif.get_ifd(34853)
        def angle(key,ref):
            d,m,s=map(float,gps[key]);return (d+m/60+s/3600)*(-1 if str(gps[ref]).upper() in ('S','W') else 1)
        if gps:
            lat,lon=geo.valid_coord(angle(2,1),angle(4,3));out.update(lat=lat,lon=lon,**geo.coordinate_formats(lat,lon))
    except (ValueError,KeyError,TypeError,AttributeError,ZeroDivisionError):pass
    return out


def run_ocr(image,local_only=False):
    if not local_only and python_path().is_file():
        stream=io.BytesIO();scaled=image.copy();scaled.thumbnail((2600,2600));scaled.convert('RGB').save(stream,'PNG')
        with OCR_LOCK:
            process=subprocess.run([str(python_path()),str(Path(__file__).parent/'tools/ocr_worker.py')],input=stream.getvalue(),capture_output=True,timeout=120,check=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        result=json.loads(process.stdout)
        return result['text'],result['scores'],result['warnings']
    global ENGINE
    try:
        import numpy as np
        from rapidocr_onnxruntime import RapidOCR
        import onnxruntime
        onnxruntime.disable_telemetry_events()
    except ImportError:
        return '',[],['OCR não instalado. Execute INSTALAR_LEITOR_FOTOS.bat e reinicie. Metadados e preenchimento manual continuam disponíveis.']
    with OCR_LOCK:
        if ENGINE is None:ENGINE=RapidOCR(intra_op_num_threads=2,inter_op_num_threads=2)
        # In-memory image, no remote OCR service and no uploads to third parties.
        scaled=image.copy();scaled.thumbnail((2600,2600))
        result,_=ENGINE(np.asarray(scaled.convert('RGB'))[:,:,::-1].copy())
    rows=sorted(result or [],key=lambda row:(round(min(p[1] for p in row[0])/15),min(p[0] for p in row[0])))
    texts=[str(row[1]) for row in rows]
    scores=[round(float(row[2]),3) for row in rows]
    return '\n'.join(texts),scores,([] if texts else ['Nenhum texto reconhecido. Confira a nitidez ou preencha os campos manualmente.'])


def analyze(data,data_dir):
    try:
        from PIL import Image,ImageOps
    except ImportError:raise ValueError('Execute INSTALAR_LEITOR_FOTOS.bat para instalar o leitor.') from None
    raw=data.get('data','')
    if not isinstance(raw,str) or len(raw)>MAX_BYTES*4//3+100:raise ValueError('Envie uma imagem de até 18 MB.')
    try:binary=base64.b64decode(raw.split(',',1)[-1],validate=True)
    except Exception:raise ValueError('Imagem em formato inválido.') from None
    if not 0<len(binary)<=MAX_BYTES:raise ValueError('Imagem vazia ou maior que 18 MB.')
    try:
        with Image.open(io.BytesIO(binary)) as im:
            if im.width*im.height>40_000_000:raise ValueError('Imagem excede 40 megapixels.')
            suffix={'JPEG':'.jpg','PNG':'.png','WEBP':'.webp'}.get(im.format)
            if suffix is None:raise ValueError('Use JPG, PNG ou WebP.')
            metadata=exif_info(im);image=ImageOps.exif_transpose(im).convert('RGB')
    except (OSError,Image.DecompressionBombError):raise ValueError('Não foi possível abrir a imagem.') from None
    try:text,scores,warnings=run_ocr(image)
    except Exception:
        text,scores,warnings='',[],['Falha no OCR local. Reinstale os recursos ou preencha os campos manualmente.']
    fields=extract_fields(text)
    if metadata.get('timestamp') and not fields['timestamp']:fields['timestamp']=metadata['timestamp']
    if 'lat' in metadata:
        if fields['coordinate_candidates'] and any(geo.distance(metadata['lat'],metadata['lon'],c['lat'],c['lon'])>50 for c in fields['coordinate_candidates']):
            fields['coordinate']='';warnings.append('GPS da imagem e texto divergem mais de 50 m. Escolha a coordenada correta.')
        elif not fields['coordinate_candidates']:fields['coordinate']=metadata['utm'] or metadata['decimal']
    if len(fields['coordinate_candidates'])>1:warnings.append('Mais de uma coordenada reconhecida. Confira qual pertence à foto.')
    for key,label in [('work_order','Obra'),('point','Ponto'),('coordinate','Coordenada')]:
        if not fields[key]:warnings.append(label+' não identificado: preencha antes de organizar.')
    ident=uuid.uuid4().hex;folder=Path(data_dir)/'leitor_fotos/entrada';folder.mkdir(parents=True,exist_ok=True)
    name=Path(str(data.get('name','foto')).replace('\\','/')).name[:200]
    record={'id':ident,'name':name,'file':ident+suffix,'sha256':hashlib.sha256(binary).hexdigest(),'text':text,'scores':scores,'exif':metadata,'suggested':fields,'warnings':warnings}
    (folder/record['file']).write_bytes(binary)
    (folder/(ident+'.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    return {**record,'preview':'/api/photo-reader/image?id='+ident}


def read_record(ident,data_dir):
    if not isinstance(ident,str) or not re.fullmatch(r'[a-f0-9]{32}',ident):raise ValueError('Foto inválida.')
    folder=Path(data_dir)/'leitor_fotos/entrada';file=folder/(ident+'.json')
    if not file.is_file():raise ValueError('Foto não encontrada. Selecione novamente.')
    record=json.loads(file.read_text(encoding='utf-8'))
    name=record.get('file','')
    if not re.fullmatch(ident+r'\.(jpg|png|webp)',name):raise ValueError('Registro de foto inválido.')
    return record,folder/name


def safe_folder(value):
    value=str(value).strip()
    if not value or len(value)>160:raise ValueError('Informe obra e ponto com até 160 caracteres.')
    clean=re.sub(r'[^A-Za-z0-9_-]+','_',unicodedata.normalize('NFKD',value).encode('ascii','ignore').decode()).strip('_')[:65] or 'registro'
    # Suffix prevents names that sanitize identically from merging different jobs.
    return clean+'_'+hashlib.sha256(value.encode()).hexdigest()[:8]


def organize(data,data_dir):
    if data.get('confirmed') is not True:raise ValueError('Confira os dados das fotos antes de organizar.')
    rows=data.get('photos')
    if not isinstance(rows,list) or not 1<=len(rows)<=100:raise ValueError('Organize de 1 a 100 fotos por lote.')
    prepared=[];seen=set()
    for row in rows:
        record,source=read_record(row.get('id'),data_dir)
        if record['id'] in seen:raise ValueError('A mesma foto aparece duas vezes no lote.')
        seen.add(record['id'])
        work=str(row.get('work_order','')).strip();point=str(row.get('point','')).strip()
        work_folder='OBRA_'+safe_folder(work);point_folder='PONTO_'+safe_folder(point)
        coord=str(row.get('coordinate','')).strip()
        if not coord and not str(row.get('location','')).strip():raise ValueError('Informe coordenada ou endereço da foto '+record['name']+'.')
        lat,lon=geo.parse_coord(coord) if coord else (None,None)
        stage=row.get('stage','Detalhe')
        if stage not in ('Antes','Depois','Detalhe'):raise ValueError('Etapa da foto inválida.')
        if file_hash(source)!=record['sha256']:raise ValueError('A foto original foi alterada. Analise novamente.')
        prepared.append((record,source,{'work_order':work,'point':point,'coordinate':geo.format_utm(lat,lon) if lat is not None else '','lat':lat,'lon':lon,'location':str(row.get('location',''))[:500],'stage':stage,'timestamp':str(row.get('timestamp',''))[:100],'folder':work_folder+'/'+point_folder}))
    ident=uuid.uuid4().hex;base=Path(data_dir)/'fotos_organizadas';base.mkdir(parents=True,exist_ok=True)
    folder_name='LOTE_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+ident
    final=base/folder_name
    with tempfile.TemporaryDirectory(prefix='.preparando-',dir=base) as tmp:
        temp=Path(tmp);items=[]
        for record,source,fields in prepared:
            relative=fields['folder']+'/'+fields['stage'].upper()+'_'+record['id']+source.suffix
            dest=temp/relative;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest)
            item={**fields,'id':record['id'],'original_name':record['name'],'sha256':record['sha256'],'photo':relative}
            dest.with_suffix('.json').write_text(json.dumps(item,ensure_ascii=False,indent=2),encoding='utf-8');items.append(item)
        manifest={'id':ident,'folder':folder_name,'photos':items,'created':datetime.now().isoformat()}
        (temp/'indice.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
        temp.rename(final)
    return {**manifest,'path':str(final)}


def file_hash(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()


def open_folder(data,data_dir):
    name=str(data.get('folder',''))
    if not re.fullmatch(r'LOTE_\d{8}_\d{6}_[a-f0-9]{32}',name):raise ValueError('Lote inválido.')
    folder=Path(data_dir)/'fotos_organizadas'/name
    if not folder.is_dir():raise ValueError('Pasta não encontrada.')
    if os.name=='nt':os.startfile(str(folder))
    return {'path':str(folder)}


def book_photos(data,data_dir):
    from book import put_media
    rows=data.get('photos',[])
    if not isinstance(rows,list) or not 1<=len(rows)<=100:raise ValueError('Selecione até 100 fotos.')
    if data.get('confirmed') is not True:raise ValueError('Confira as fotos primeiro.')
    result=[];work=str(data.get('work_order','')).strip()
    if not work:raise ValueError('Informe a obra atual.')
    for row in rows:
        if str(row.get('work_order','')).strip()!=work:raise ValueError('Anexe somente fotos da obra atual.')
        record,source=read_record(row.get('id'),data_dir)
        point=str(row.get('point','')).strip();safe_folder(point)
        coord=str(row.get('coordinate','')).strip()
        if not coord and not str(row.get('location','')).strip():raise ValueError('Informe coordenada ou endereço.')
        lat,lon=geo.parse_coord(coord) if coord else (None,None)
        if file_hash(source)!=record['sha256']:raise ValueError('Foto alterada. Analise novamente.')
        ref=put_media({'name':record['name'],'data':base64.b64encode(source.read_bytes()).decode()},Path(data_dir)/'media')
        if row.get('stage','Detalhe') not in ('Antes','Depois','Detalhe'):raise ValueError('Etapa inválida.')
        result.append({'point':point,'coordinate':geo.format_utm(lat,lon) if lat is not None else '','lat':lat,'lon':lon,'photo':{**ref,'caption':str(row.get('location',''))[:500],'stage':row.get('stage','Detalhe')}})
    return {'photos':result}


def group_photos(data):
    """Greedy anchored groups, per work order; never join via distant chains."""
    import math
    mode=data.get('mode','radius')
    if mode not in ('radius','address'):raise ValueError('Modo de agrupamento inválido.')
    radius=data.get('radius_m',25)
    if isinstance(radius,bool):raise ValueError('Raio inválido.')
    try:radius=float(radius)
    except (ValueError,TypeError):raise ValueError('Raio inválido.') from None
    if not math.isfinite(radius) or not 5<=radius<=500:raise ValueError('Escolha um raio de 5 a 500 metros.')
    rows=data.get('photos')
    if not isinstance(rows,list) or not 1<=len(rows)<=100:raise ValueError('Selecione de 1 a 100 fotos.')
    valid=[];excluded=[];seen=set()
    for row in rows:
        ident=row.get('id')
        if not isinstance(ident,str) or not re.fullmatch('[a-f0-9]{32}',ident) or ident in seen:raise ValueError('Foto inválida ou repetida.')
        seen.add(ident);work=str(row.get('work_order','')).strip()
        try:
            if not work:raise ValueError('Informe a obra.')
            address=str(row.get('location','')).strip()[:500]
            if mode=='radius':lat,lon=geo.parse_coord(str(row.get('coordinate','')))
            else:
                if not normalize_address(address):raise ValueError('Informe endereço.')
                lat,lon=None,None
            valid.append({'id':ident,'work_order':work,'lat':lat,'lon':lon,'point':str(row.get('point','')).strip(),'address':address,'address_key':normalize_address(address)})
        except ValueError:excluded.append(ident)
    groups=[]
    for row in sorted(valid,key=lambda r:(r['work_order'],r['address_key'] if mode=='address' else r['lat'],r['lon'] or 0,r['id'])):
        candidates=[(0 if mode=='address' else geo.distance(g['lat'],g['lon'],row['lat'],row['lon']),i) for i,g in enumerate(groups) if g['work_order']==row['work_order'] and (mode!='address' or g['address_key']==row['address_key'])]
        candidates=[(d,i) for d,i in candidates if d<=radius]
        if candidates:
            distance,index=min(candidates);group=groups[index];group['max_distance_m']=max(group['max_distance_m'],distance)
        else:
            group={'work_order':row['work_order'],'lat':row['lat'],'lon':row['lon'],'ids':[],'labels':set(),'max_distance_m':0,'address':row['address'],'address_key':row['address_key']};groups.append(group)
        group['ids'].append(row['id'])
        if row['point']:group['labels'].add(row['point'])
    used={r['point'] for r in valid if r['point']};counter=1
    for group in groups:
        labels=sorted(group.pop('labels'));group['recognized_points']=labels
        group['conflict']=len(labels)>1
        if len(labels)==1:group['point']=labels[0]
        elif not labels:
            while f'G{counter:02d}' in used:counter+=1
            group['point']=f'G{counter:02d}';used.add(group['point']);counter+=1
        else:group['point']=''
        group['max_distance_m']=round(group['max_distance_m'],2)
    for group in groups:
        if group['point'] and sum(g['work_order']==group['work_order'] and g['point']==group['point'] for g in groups)>1:
            group['conflict']=True
            group['warning']='Mesmo ponto em grupos distantes. Confira e diferencie os nomes antes de aplicar.'
    return {'mode':mode,'radius_m':radius,'groups':groups,'excluded':excluded}


def normalize_address(address):
    text=unicodedata.normalize('NFKD',str(address)).encode('ascii','ignore').decode().casefold()
    text=re.sub(r'[^a-z0-9]+',' ',text).strip()
    text=re.sub(r'^av\b','avenida',text);text=re.sub(r'^r\b','rua',text)
    return ' '.join(text.split())


def analyze_zip(data,data_dir):
    raw=data.get('data','')
    if not isinstance(raw,str) or len(raw)>70_000_000:raise ValueError('ZIP limitado a 50 MB.')
    try:binary=base64.b64decode(raw,validate=True)
    except Exception:raise ValueError('ZIP inválido.') from None
    if len(binary)>50*1024*1024:raise ValueError('ZIP limitado a 50 MB.')
    try:
        with zipfile.ZipFile(io.BytesIO(binary)) as archive:
            entries=archive.infolist()
            if len(entries)>1000:raise ValueError('ZIP com entradas demais; use até 100 fotos.')
            images=[];total=0
            for entry in entries:
                path=PurePosixPath(entry.filename.replace('\\','/'))
                if path.is_absolute() or '..' in path.parts or ':' in entry.filename or stat.S_ISLNK(entry.external_attr>>16):raise ValueError('ZIP contém caminho ou link inseguro.')
                if entry.flag_bits&1:raise ValueError('ZIP protegido por senha não é aceito.')
                if entry.is_dir() or path.suffix.lower() not in ('.jpg','.jpeg','.png','.webp'):continue
                if entry.file_size>MAX_BYTES:raise ValueError('Uma foto no ZIP excede 18 MB.')
                total+=entry.file_size;images.append(entry)
            available=data.get('available',100)
            if not isinstance(available,int) or isinstance(available,bool) or not 1<=available<=100:raise ValueError('Limpe a lista para importar mais fotos.')
            if not 1<=len(images)<=available:raise ValueError('O ZIP excede as vagas da lista ou não contém fotos aceitas. Limite: '+str(available)+' fotos.')
            if total>200*1024*1024:raise ValueError('Fotos descompactadas excedem 200 MB.')
            results=[];errors=[]
            for entry in images:
                try:results.append(analyze({'name':PurePosixPath(entry.filename).name,'data':base64.b64encode(archive.read(entry)).decode()},data_dir))
                except (ValueError,OSError,zipfile.BadZipFile) as error:errors.append({'name':entry.filename,'error':str(error)})
            return {'photos':results,'errors':errors}
    except zipfile.BadZipFile:raise ValueError('ZIP inválido ou corrompido.') from None
