"""Validação e cálculo do book de obra e da somagem de condutores."""
import base64
import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlencode
from engine import calculate, decimal_text
from geo import parse_coord, format_utm, coordinate_for_book
from location_tools import clean_features
from drawing import clean_drawing
from repository import normalize_repository

LEGACY_FORMS_URL='https://teams.microsoft.com/l/message/19:2f95e394-cfb6-41e0-9448-906a1b942f03_9a8fb881-664f-4854-b25a-f6d868824029@unq.gbl.spaces/1791913041803?context=%7B%22contextType%22%3A%22chat%22%7D'
DEFAULT_FORMS_URL='https://forms.cloud.microsoft/Pages/ResponsePage.aspx?id=hoDG-Fy5y0mdOO03lAq-9eWyRm5PvkRKkhBxMcQVKxxUMzNRRzNHNlFFUkswRVg0TjRXUzhaOFNPUy4u&b2b=true'
DEFAULT_SETTINGS={'forms_url':DEFAULT_FORMS_URL,'repository':'https://github.com/Bl4ckF/fechamento_obra','branch':'main','radius_m':1200,'map_base':'Satélite','sync_enabled':True,'sync_branch':'registros-materiais'}
MEDIA_RE=re.compile(r'^[a-f0-9]{64}\.(jpg|png|webp)$')
PDF_RE=re.compile(r'^[a-f0-9]{64}\.pdf$')
ASSET_RE=re.compile(r'^[a-f0-9]{64}\.(jpg|png|webp|pdf)$')

def text(value,limit=1000):return str(value or '').strip()[:limit]

def clean_url(value):
    url=text(value,3000)
    if not url:return ''
    p=urlparse(url)
    if p.scheme!='https' or not p.netloc or p.username or p.password:raise ValueError('Use um endereço HTTPS válido.')
    return url

def forms_url(value):
    url=text(value,20000).replace('\\&','&')
    if url==LEGACY_FORMS_URL:return DEFAULT_FORMS_URL
    parsed=urlparse(url)
    if parsed.hostname=='login.microsoftonline.com':
        try:
            state=parse_qs(parsed.query)['state'][0]
            decoded=json.loads(base64.urlsafe_b64decode(state+'='*((-len(state))%4)))
            target=decoded['data']['.redirect'];p=urlparse(target)
            if p.scheme!='https' or p.hostname not in ('forms.cloud.microsoft','forms.office.com'):raise ValueError()
            params=parse_qs(p.query)
            return clean_url('https://'+p.hostname+'/Pages/ResponsePage.aspx?'+urlencode({'id':params['id'][0],'b2b':'true'}))
        except (ValueError,KeyError,TypeError):
            raise ValueError('Cole o link direto do Forms; não foi possível recuperar o formulário deste endereço de login.')
    return clean_url(url)

def clean_settings(data):
    out=dict(DEFAULT_SETTINGS)
    out['forms_url']=forms_url(data.get('forms_url',out['forms_url']))
    out['repository']=normalize_repository(data.get('repository',out['repository']))
    separate=str(data.get('records_repository') or '').strip()
    out['records_repository']=normalize_repository(separate) if separate else ''
    branch=text(data.get('branch','main'),100)
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_./-]*',branch) or '..' in branch:raise ValueError('Nome de branch inválido.')
    out['branch']=branch
    sync_branch=text(data.get('sync_branch','registros-materiais'),100)
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_/-]*',sync_branch) or '..' in sync_branch or '//' in sync_branch or sync_branch.endswith('/') or sync_branch==branch:
        raise ValueError('Use uma branch de registros válida e diferente da branch do programa.')
    out['sync_branch']=sync_branch
    out['sync_enabled']=data.get('sync_enabled',True) is True
    try:out['radius_m']=int(data.get('radius_m',1200))
    except (ValueError,TypeError):raise ValueError('Informe o raio da busca em metros.')
    if not 50<=out['radius_m']<=20000:raise ValueError('O raio deve estar entre 50 e 20.000 metros.')
    out['map_base']=data.get('map_base') if data.get('map_base') in ('Satélite','Mapa','Sem fundo') else 'Satélite'
    return out

def media_bytes(data):
    raw=data.get('data','')
    if not isinstance(raw,str) or len(raw)>43_000_000:raise ValueError('Imagem muito grande. Use uma imagem de até 32 MB.')
    if raw.startswith('data:'):raw=raw.split(',',1)[-1]
    try:binary=base64.b64decode(raw,validate=True)
    except Exception:raise ValueError('Imagem inválida.')
    if not 12<len(binary)<=32_000_000:raise ValueError('Tamanho de imagem inválido (limite 32 MB).')
    ext='png' if binary.startswith(b'\x89PNG\r\n\x1a\n') else 'jpg' if binary.startswith(b'\xff\xd8\xff') else 'webp' if binary[:4]==b'RIFF' and binary[8:12]==b'WEBP' else None
    if not ext:raise ValueError('Use fotos JPG, PNG ou WebP.')
    return hashlib.sha256(binary).hexdigest()+'.'+ext,binary

def put_media(data,folder):
    name,binary=media_bytes(data)
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    dest=folder/name
    if not dest.exists():dest.write_bytes(binary)
    return {'ref':name,'name':text(data.get('name','Imagem'),200),'size':len(binary)}

def pdf_bytes(data):
    raw=data.get('data','')
    if not isinstance(raw,str) or len(raw)>70_000_000:raise ValueError('Use um PDF de até 50 MB.')
    if raw.startswith('data:'):raw=raw.split(',',1)[-1]
    try:binary=base64.b64decode(raw,validate=True)
    except Exception:raise ValueError('PDF inválido.')
    if not 12<len(binary)<=50*1024*1024 or not binary.startswith(b'%PDF-'):raise ValueError('PDF inválido ou maior que 50 MB.')
    return hashlib.sha256(binary).hexdigest()+'.pdf',binary

def put_pdf(data,folder):
    name,binary=pdf_bytes(data);folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    dest=folder/name
    if not dest.exists():dest.write_bytes(binary)
    return {'ref':name,'name':text(data.get('name','Projeto.pdf'),200),'size':len(binary)}

def asset_bytes(data):
    return pdf_bytes(data) if PDF_RE.fullmatch(str(data.get('ref',''))) else media_bytes(data)

def pdf_ref(value,available=None):
    ref=text(value,100)
    if not PDF_RE.fullmatch(ref):raise ValueError('Referência do PDF original inválida.')
    if available is not None and ref not in available:raise ValueError('O PDF original não está disponível. Importe o backup completo ou o projeto novamente.')
    return ref

def photo_ref(value,available=None):
    ref=text(value,100)
    if not MEDIA_RE.fullmatch(ref):raise ValueError('Referência de foto inválida.')
    if available is not None and ref not in available:raise ValueError('Uma foto ou croqui não está disponível. Importe o backup completo ou adicione a imagem novamente.')
    return ref

def number(value,label,zero=False):
    try:n=Decimal(str(value).strip().replace(',','.'))
    except (InvalidOperation,ValueError):raise ValueError(label+': informe um número válido.')
    if not n.is_finite() or n<0 or (not zero and n==0) or n>1_000_000 or (n!=0 and n<Decimal('.000001')):raise ValueError(label+': quantidade fora do intervalo permitido.')
    return n

def normalize_book(raw,services,available=None):
    if raw is None:return None
    if not isinstance(raw,dict):raise ValueError('Book inválido.')
    points=raw.get('points',[]);conductors=raw.get('conductors',[])
    if not isinstance(points,list) or len(points)>500:raise ValueError('Limite de 500 pontos por book.')
    if not isinstance(conductors,list) or len(conductors)>2000:raise ValueError('Limite de 2.000 trechos de condutores.')
    clean=[];ids=set();names=set();pending=[]
    for index,p in enumerate(points):
        if not isinstance(p,dict):raise ValueError('Ponto inválido.')
        ident=text(p.get('id'),80);label=text(p.get('number'),60)
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',ident) or ident in ids:raise ValueError('Identificador do ponto inválido ou repetido.')
        if not label:raise ValueError(f'Informe o número do ponto {index+1}.')
        if label.casefold() in names:raise ValueError('Número de ponto repetido: '+label)
        ids.add(ident);names.add(label.casefold())
        point={'id':ident,'number':label}
        for k,limit in [('coordinate',200),('td',100),('rd',100),('circuit',100),('notes',6000),('installed',3000),('removed',3000),('patrimony',100),('serial',100),('voltage',100),('power',100),('impedance',100),('manufacturer',200),('manufactured',100)]:point[k]=text(p.get(k),limit)
        if point['coordinate']:
            point['lat'],point['lon']=parse_coord(point['coordinate'])
            point['coordinate']=format_utm(point['lat'],point['lon'])
        else:point['lat']=point['lon']=None
        point['network_source']='proximidade' if p.get('network_source')=='proximidade' else 'informado'
        point['photos']=[]
        photos=p.get('photos',[])
        if not isinstance(photos,list) or len(photos)>30:raise ValueError('Limite de 30 fotos por ponto.')
        for photo in photos:
            point['photos'].append({'ref':photo_ref(photo.get('ref'),available),'name':text(photo.get('name'),200),'caption':text(photo.get('caption'),500),'stage':photo.get('stage') if photo.get('stage') in ('Antes','Depois','Detalhe') else 'Detalhe'})
        if not photos:pending.append('Ponto '+label+': adicione ao menos uma foto.')
        point['materials']=calculate([s for s in services if s.get('point_id')==ident])['materials']
        clean.append(point)
    if not points:pending.append('Cadastre os pontos da obra.')
    for i,s in enumerate(services):
        if s.get('point_id') and s['point_id'] not in ids:raise ValueError(f'Serviço {i+1}: o ponto vinculado não existe.')
        if not s.get('point_id'):pending.append(f'Serviço {i+1}: vincule a um ponto do book.')
    rows=[];totals={}
    for c in conductors:
        row={k:text(c.get(k),200 if k!='description' else 500) for k in ('id','from_point','to_point','code','description','gauge','notes')}
        if row['from_point'] not in ids or row['to_point'] not in ids or row['from_point']==row['to_point']:raise ValueError('Condutores: selecione dois pontos diferentes e existentes.')
        if not row['description']:raise ValueError('Informe o tipo/descrição do condutor.')
        if c.get('movement') not in ('instalado','desativado'):raise ValueError('Escolha a movimentação do condutor.')
        length=number(c.get('length'),'Comprimento');count=number(c.get('count'),'Número de condutores');extra=number(c.get('extra','0'),'Acréscimo',True)
        if count!=int(count) or count>100:raise ValueError('Número de condutores deve ser um inteiro de 1 a 100.')
        total=length*count+extra
        row.update(movement=c['movement'],length=decimal_text(length),count=int(count),extra=decimal_text(extra),total=decimal_text(total))
        rows.append(row)
        key=(row['code'],row['description'].casefold(),row['gauge'].casefold(),row['movement'])
        if key not in totals:totals[key]={'code':row['code'],'description':row['description'],'gauge':row['gauge'],'movement':row['movement'],'total':Decimal(0)}
        totals[key]['total']+=total
    no_conductors=raw.get('no_conductors') is True
    if rows and no_conductors:raise ValueError('Existem condutores lançados: desmarque "Sem movimentação de condutores".')
    if not rows and not no_conductors:pending.append('Informe os condutores ou marque que não houve movimentação.')
    for t in totals.values():t['total']=decimal_text(t['total'])
    pages=raw.get('croqui_pages')
    if pages is None:pages=[{'id':'croqui_1','croqui':raw.get('croqui'),'drawing':raw.get('drawing')}] if raw.get('croqui') or raw.get('drawing') else []
    if not isinstance(pages,list) or len(pages)>100:raise ValueError('Limite de 100 páginas de croqui por obra.')
    croqui_pages=[];page_ids=set()
    for index,page in enumerate(pages):
        if not isinstance(page,dict):raise ValueError('Página do croqui inválida.')
        ident=text(page.get('id'),80)
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',ident) or ident in page_ids:raise ValueError('Identificador de página inválido ou repetido.')
        page_ids.add(ident);croqui=page.get('croqui') or None
        if croqui:
            if not isinstance(croqui,dict):raise ValueError('Imagem do croqui inválida.')
            croqui={'ref':photo_ref(croqui.get('ref'),available),'name':text(croqui.get('name'),200),'caption':text(croqui.get('caption'),2000)}
        else:pending.append(f'Página {index+1} do croqui: aguarde o salvamento da imagem.')
        clean_page={'id':ident,'croqui':croqui,'drawing':clean_drawing(page.get('drawing'),available)}
        if page.get('image_pending') is True:
            clean_page['image_pending']=True
            if croqui:pending.append(f'Página {index+1} do croqui: aguarde o salvamento da imagem atualizada.')
        croqui_pages.append(clean_page)
    if not croqui_pages:pending.append('Adicione o croqui da obra.')
    first=croqui_pages[0] if croqui_pages else {}
    return {'geography':clean_features(raw.get('geography',[])),'points':clean,'conductors':rows,'conductor_totals':list(totals.values()),'no_conductors':no_conductors,'croqui_pages':croqui_pages,'croqui':first.get('croqui'),'drawing':first.get('drawing'),'forms_submitted':raw.get('forms_submitted') is True,'forms_note':text(raw.get('forms_note'),1000),'pending':pending,'ready':not pending}

def summary_text(job):
    b=job.get('book') or {};lines=[f"OBRA / OS: {job['work_order']}",f"DATA: {job.get('date','')}",f"RESPONSÁVEL: {job.get('responsible','')}",f"LOCAL: {job.get('location','')}",f"PONTOS: {len(b.get('points',[]))}"]
    for p in b.get('points',[]):
        lines.extend(['',f"PONTO {p['number']} | {coordinate_for_book(p)}",f"TD: {p['td']} | Religador: {p['rd']} | Circuito: {p['circuit']}"])
        for movement,label in [('instalado','INSTALADOS'),('desativado','DESATIVADOS')]:
            lines.append(label+': '+ '; '.join(f"{m['code']} {m['description']} = {m['quantity']} {m['unit']}" for m in p['materials'] if m['movement']==movement))
        if p['installed']:lines.append('Instalação: '+p['installed'])
        if p['removed']:lines.append('Desativação: '+p['removed'])
    lines.extend(['','CONDUTORES:'])
    for t in b.get('conductor_totals',[]):lines.append(f"{t['movement']} | {t['code']} {t['description']} {t['gauge']} | {t['total']} m")
    if b.get('no_conductors'):lines.append('Sem movimentação de condutores.')
    if job.get('notes'):lines.extend(['','OBSERVAÇÕES: '+job['notes']])
    return '\n'.join(lines)
