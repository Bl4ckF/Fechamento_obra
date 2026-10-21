"""Servidor local. Python 3.9+; somente biblioteca padrão."""
import argparse
import base64
import csv
from decimal import Decimal
import io
import json
import os
import secrets
import sqlite3
import threading
import uuid
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from engine import CATALOG, LABOR, ROOT, BASE_DATA, calculate, clean_profile, suggestions
from pricing import clean_price, price_source
from compositions import base_editor, base_summaries, context_key, memory_payload, normalize_memory
from book import (DEFAULT_SETTINGS, ASSET_RE, clean_settings, normalize_book, put_media, put_pdf, asset_bytes, summary_text)
from book_report import book_html, materials_report_html
import geo
from drawing import symbol_catalog
from symbols import clean_symbol
import updates
import learning
import job_files
import diagnostics
from records_sync import RecordSync

APP_ID='engelmig-fechamento-v1'
VERSION='1.3.7'
LEARNING_LOCK=threading.RLock()
TOKEN=secrets.token_urlsafe(32)
INSTANCE_ID=uuid.uuid4().hex
DATA_DIR=Path(os.environ.get('ENGELMIG_DATA_DIR',ROOT/'dados'))
DB=DATA_DIR/'fechamento.sqlite3'
SYNC=None

def now(): return datetime.now().astimezone().isoformat(timespec='seconds')

def connect():
    DATA_DIR.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(DB,timeout=20)
    db.execute('CREATE TABLE IF NOT EXISTS profiles (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS memories (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS memory_history (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS settings (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS drafts (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS work_drafts (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS cleared_drafts (id TEXT PRIMARY KEY, cleared_at TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS custom_symbols (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
    learning.ensure(db)
    return db

def records(table):
    with connect() as db: return [json.loads(r[0]) for r in db.execute(f'SELECT payload FROM {table} ORDER BY rowid DESC')]

def save_record(table, record):
    with connect() as db:
        db.execute(f'INSERT OR REPLACE INTO {table} (id,payload) VALUES (?,?)',(record['id'],json.dumps(record,ensure_ascii=False)))

def save_symbol(data):
    symbol=clean_symbol(data.get('symbol'),draft=True)
    expected=data.get('expected_revision',0)
    if not isinstance(expected,int) or expected<0:raise ValueError('Revisão da simbologia inválida.')
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT payload FROM custom_symbols WHERE id=?',(symbol['id'],)).fetchone()
        revision=json.loads(row[0]).get('revision',0) if row else 0
        if expected!=revision:raise ValueError('Esta simbologia foi alterada em outra janela. Reabra o editor ou crie uma cópia para preservar suas alterações.')
        if not row and db.execute('SELECT COUNT(*) FROM custom_symbols').fetchone()[0]>=1000:raise ValueError('Limite de 1.000 simbologias pessoais atingido.')
        symbol.update(revision=revision+1,updated_at=now())
        db.execute('INSERT OR REPLACE INTO custom_symbols VALUES (?,?)',(symbol['id'],json.dumps(symbol,ensure_ascii=False)))
    return symbol

def settings():
    rows=records('settings')
    return clean_settings({**DEFAULT_SETTINGS,**(rows[0] if rows else {})})

def record_sync():
    global SYNC
    if SYNC is None:
        def export_events():
            with LEARNING_LOCK,connect() as db:return learning.sync_events(db)
        def import_events(events):
            with LEARNING_LOCK,connect() as db:
                result=learning.import_records(db,{'schema':1,'kind':'registros_ajustes','events':events})
                learning.write_named_exports(db,DATA_DIR)
                return result
        SYNC=RecordSync(DATA_DIR,settings,export_events,import_events)
    return SYNC

def available_media():
    folder=DATA_DIR/'media'
    return {p.name for p in folder.glob('*') if ASSET_RE.fullmatch(p.name)} if folder.exists() else set()

def backup_payload():
    media=[{'ref':name,'data':base64.b64encode((DATA_DIR/'media'/name).read_bytes()).decode('ascii')} for name in sorted(available_media())]
    with connect() as db:learned=learning.export_records(db)
    return {'app':APP_ID,'schema':4,'version':VERSION,'created_at':now(),'profiles':records('profiles'),'jobs':records('jobs'),'memories':records('memories'),'memory_history':records('memory_history'),'media':media,'custom_symbols':records('custom_symbols'),'settings':settings(),'drafts':records('drafts'),'work_drafts':records('work_drafts'),'learning':learned}

def learning_bootstrap():
    with LEARNING_LOCK,connect() as db:
        learning.backfill(db,records('jobs'),records('memories'))
        return learning.patterns(db)

def automatic_draft(data):
    data.update(id='current',updated_at=learning.stamp())
    with LEARNING_LOCK,connect() as db:
        if isinstance(data.get('draft_id'),str) and db.execute('SELECT 1 FROM cleared_drafts WHERE id=?',(data['draft_id'],)).fetchone():
            raise ValueError('Este rascunho foi limpo. Recarregue a página para continuar com um novo fechamento.')
        learning.put(db,'drafts',data)
        if data.get('draft_id') and (data.get('work_order') or data.get('services') or data.get('editor') or (data.get('book') or {}).get('points') or (data.get('book') or {}).get('croqui_pages') or (data.get('book') or {}).get('croqui')):
            learning.put(db,'work_drafts',{**data,'id':'draft_'+learning.digest(data['draft_id'])})
        result=learning.capture(db,data)
    try:
        with LEARNING_LOCK,connect() as db:learning.write_named_exports(db,DATA_DIR)
    except OSError:
        result['export_warning']='Rascunho e histórico salvos no banco; não foi possível atualizar a cópia por responsável.'
    return {'ok':True,'updated_at':data['updated_at'],'learning':result}

def cleared_draft_ids():
    with connect() as db:return [row[0] for row in db.execute('SELECT id FROM cleared_drafts')]

def clear_draft(data):
    ident=data.get('draft_id')
    if not isinstance(ident,str) or not 1<=len(ident)<=400:raise ValueError('Identifique o rascunho que será limpo.')
    stamp=learning.stamp()
    blank={'id':'current','draft_id':str(uuid.uuid4()),'updated_at':stamp,'work_order':'','responsible':'',
           'location':'','notes':'','date':str(data.get('date',''))[:30],'services':[],'book':None,
           'selected':None,'editor':None,'editing':-1,'editor_touched':False}
    with LEARNING_LOCK,connect() as db:
        db.execute('INSERT OR REPLACE INTO cleared_drafts VALUES (?,?)',(ident,stamp))
        db.execute('DELETE FROM work_drafts WHERE id=?',('draft_'+learning.digest(ident),))
        learning.put(db,'drafts',blank)
    return {'ok':True,'draft':blank}

def remember(data):
    key=context_key(data)
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        old=db.execute('SELECT payload FROM memories WHERE id=?',(key,)).fetchone()
        previous=json.loads(old[0]) if old else None
        record,changed=memory_payload(data,previous)
        if changed:
            record['updated_at']=now()
            event={'id':uuid.uuid4().hex,'memory_id':key,'action':'learn','saved_at':now(),'before':previous,'after':record}
            db.execute('INSERT OR REPLACE INTO memories VALUES (?,?)',(key,json.dumps(record,ensure_ascii=False)))
            db.execute('INSERT INTO memory_history VALUES (?,?)',(event['id'],json.dumps(event,ensure_ascii=False)))
    return record

def load_base(data):
    result=base_editor(data)
    key=context_key(result['editor'])
    with connect() as db:r=db.execute('SELECT payload FROM memories WHERE id=?',(key,)).fetchone()
    memory=json.loads(r[0]) if r and not data.get('original') else None
    if memory:
        result['editor']=dict(memory['editor'],quantity='1',reviewed=False)
        if memory.get('source_hash')!=BASE_DATA['source_sha256']:
            result['warnings'].append('A origem mudou desde o último ajuste. Compare a memória com a base antes de conferir.')
    result['memory']=memory
    result['memory_key']=key
    if not data.get('original') and data.get('responsible') is not None:
        with connect() as db:learned=learning.select(db,{**result['editor'],'responsible':data.get('responsible','')})
        if learned['editor']:
            result['editor']={**learned['editor'],'quantity':'1','reviewed':False}
            result['learning_source']=learned['source'];result['memory']=None
    result.pop('base')
    return result

def forget_memory(key):
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT payload FROM memories WHERE id=?',(key,)).fetchone()
        if not row:raise ValueError('Memória não encontrada.')
        previous=json.loads(row[0])
        event={'id':uuid.uuid4().hex,'memory_id':key,'action':'forget','saved_at':now(),'before':previous,'after':None}
        db.execute('DELETE FROM memories WHERE id=?',(key,))
        db.execute('INSERT INTO memory_history VALUES (?,?)',(event['id'],json.dumps(event,ensure_ascii=False)))
    return {'ok':True}

def recover_memory(event_id):
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT payload FROM memory_history WHERE id=?',(event_id,)).fetchone()
        if not row:raise ValueError('Revisão não encontrada.')
        event=json.loads(row[0]);chosen=event.get('after') or event.get('before')
        if not chosen:raise ValueError('Esta revisão não contém uma composição.')
        key=context_key(chosen['editor'])
        old=db.execute('SELECT payload FROM memories WHERE id=?',(key,)).fetchone()
        previous=json.loads(old[0]) if old else None
        record,_=memory_payload(chosen['editor'],previous)
        record['updated_at']=now()
        new_event={'id':uuid.uuid4().hex,'memory_id':key,'action':'recover','saved_at':now(),'before':previous,'after':record}
        db.execute('INSERT OR REPLACE INTO memories VALUES (?,?)',(key,json.dumps(record,ensure_ascii=False)))
        db.execute('INSERT INTO memory_history VALUES (?,?)',(new_event['id'],json.dumps(new_event,ensure_ascii=False)))
    return record

def backup_database():
    folder=DATA_DIR/'backups'
    folder.mkdir(exist_ok=True)
    name=folder/f"antes_restauracao_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}.sqlite3"
    with connect() as src,sqlite3.connect(name) as dest: src.backup(dest)

def safe_cell(value):
    text=str(value)
    return "'"+text if text.lstrip().startswith(('=','+','-','@')) else text

def report_csv(job):
    out=io.StringIO(newline='')
    writer=csv.writer(out,delimiter=';')
    def row(values): writer.writerow([safe_cell(x) for x in values])
    row(['MÃO DE OBRA E MATERIAIS','Engelmig - Campo Grande/MS'])
    points={p['id']:p['number'] for p in (job.get('book') or {}).get('points',[])}
    row(['Obra / OS',job['work_order'],'Situação',job['status']])
    row(['Data',job.get('date',''),'Responsável',job.get('responsible','')])
    row(['Local',job.get('location','')]); row(['Observações',job.get('notes','')])
    row([]);row(['MATERIAIS']);row(['Movimentação','Código','Descrição','Unidade','Quantidade','Origem'])
    for m in job['result']['materials']:
        row([m['movement'].upper(),m['code'],m['description'],m['unit'],m['quantity'].replace('.',','),' | '.join(m['services'])])
    row([]);row(['MÃO DE OBRA']);row(['Código','Operação','Escopo','Descrição','Quantidade','Composição','Conferida','US unitária','Ponto'])
    for s in job['result']['services']:
        row([s['code'],s['operation'],s['scope'],s['description'],s['quantity'].replace('.',','),s['variant'],'Sim' if s['reviewed'] else 'Não','' if s['us'] is None else str(s['us']).replace('.',','),points.get(s.get('point_id'),'Sem ponto')])
    row([]);row(['MATERIAIS POR MÃO DE OBRA']);row(['Item do serviço','Ponto','Código MO','Operação','Quantidade MO','Código material','Material','Movimentação','Unidade','Por MO','Total'])
    for index,s in enumerate(job['result']['services'],1):
        for m in s['materials']:
            total=Decimal(m['coefficient'])*Decimal(s['quantity'])
            row([index,points.get(s.get('point_id'),'Sem ponto'),s['code'],s['operation'],s['quantity'].replace('.',','),m['code'],m['description'],m['movement'],m['unit'],m['coefficient'].replace('.',','),format(total,'f').replace('.',',')])
    if job['result']['pending']:
        row([]);row(['PENDÊNCIAS'])
        for text in job['result']['pending']: row([text])
    return ('\ufeff'+out.getvalue()).encode('utf-8')

def preview_book(payload):
    """Render the current draft without saving jobs, samples, or media."""
    result=calculate(payload.get('services',[]))
    book=normalize_book(payload.get('book') or {},result['services'],available_media())
    job={'result':result,'book':book,'status':'rascunho'}
    for key,limit in [('work_order',120),('date',30),('responsible',160),('location',500),('notes',4000)]:
        job[key]=str(payload.get(key,'') or '')[:limit]
    pending=list(result.get('pending',[]))+list(book.get('pending',[]))
    return {'html':book_html(job,preview=True).decode('utf-8'),'pending':pending}

def save_job(payload):
    result=calculate(payload.get('services',[]))
    if not result['services']: raise ValueError('Adicione ao menos um serviço.')
    work_order=str(payload.get('work_order','')).strip()[:120]
    if not work_order: raise ValueError('Informe o número da obra / OS.')
    status='fechado' if payload.get('status')=='fechado' else 'rascunho'
    if status=='fechado' and not result['ready']: raise ValueError('Confira as composições e resolva as pendências antes de fechar.')
    book=normalize_book(payload.get('book'),result['services'],available_media())
    if status=='fechado' and book and not book['ready']:raise ValueError('Complete o book: '+' '.join(book['pending']))
    # New immutable record per save; re-opening never silently changes an earlier report.
    job={'id':uuid.uuid4().hex,'saved_at':now(),'work_order':work_order,'status':status,'result':result}
    for key,limit in [('date',30),('responsible',160),('location',500),('notes',4000),('draft_id',100)]: job[key]=str(payload.get(key,''))[:limit]
    if book:
        job['book']=book
        job['workflow']='concluido' if status=='fechado' and book['forms_submitted'] else 'aguardando_forms' if status=='fechado' else 'rascunho'
        job['forms_url']=settings()['forms_url']
    if payload.get('source_job_id'):
        source_id=str(payload['source_job_id'])
        if any(j['id']==source_id for j in records('jobs')):job['source_job_id']=source_id
    save_record('jobs',job)
    with LEARNING_LOCK,connect() as db:
        learning.capture(db,{**job,'services':result['services']},'obra salva',record_id='job:'+job['id'])
        learning.write_named_exports(db,DATA_DIR)
    try:
        folder=ensure_job_folder(job)
        job['folder']=str(folder)
    except OSError as exc:
        job['folder_error']='Registro salvo. Não foi possível criar a pasta: '+str(exc)
    return job

def ensure_job_folder(job):
    return job_files.ensure_files(job,DATA_DIR,ROOT/'web',book_html(job),materials_report_html(job),report_csv(job))

def open_job_folder(data):
    job=next((j for j in records('jobs') if j['id']==str(data.get('id',''))),None)
    if not job:raise ValueError('Registro de obra não encontrado.')
    section=data.get('section','root')
    if section not in ('root','photos'):raise ValueError('Pasta do registro inválida.')
    folder=ensure_job_folder(job)
    if section=='photos':folder=folder/'fotos'
    opened=job_files.open_folder(folder)
    return {'opened':opened,'path':str(folder),'message':'Pasta aberta.' if opened else 'Pasta: '+str(folder)}

def restore(payload):
    if payload.get('app')!=APP_ID or payload.get('schema') not in (1,2,3,4): raise ValueError('Arquivo de backup incompatível.')
    media=payload.get('media',[])
    if not isinstance(media,list) or len(media)>20000:raise ValueError('Fotos do backup inválidas.')
    prepared=[];available=available_media()
    for m in media:
        name,binary=asset_bytes(m)
        if name!=m.get('ref'):raise ValueError('Uma foto do backup está corrompida.')
        prepared.append((name,binary));available.add(name)
    profiles=payload.get('profiles'); jobs=payload.get('jobs')
    if not isinstance(profiles,list) or not isinstance(jobs,list) or len(profiles)>10000 or len(jobs)>10000:
        raise ValueError('Conteúdo de backup inválido.')
    cleaned=[]
    for p in profiles:
        c=clean_profile(p); c.update(id=str(p.get('id') or uuid.uuid4().hex),updated_at=str(p.get('updated_at') or now()))
        cleaned.append(c)
    checked_jobs=[]
    for j in jobs:
        if not isinstance(j,dict) or not j.get('id') or not j.get('work_order') or j.get('status') not in ('rascunho','fechado'):
            raise ValueError('Registro de obra inválido no backup.')
        previous_services=j.get('result',{}).get('services',[])
        calc=calculate(previous_services)
        for original,normalized in zip(previous_services,calc['services']):
            if 'unit_price' in original:
                normalized['unit_price']=clean_price(original['unit_price'])
                normalized['price_source']=price_source(original.get('price_source'))
            else:
                normalized.pop('unit_price',None)
                normalized.pop('price_source',None)
        if not calc['services'] or (j['status']=='fechado' and not calc['ready']): raise ValueError('Obra inválida no backup.')
        checked_jobs.append({**j,'result':calc})
        if j.get('book') is not None:
            checked_jobs[-1]['book']=normalize_book(j['book'],calc['services'],available)
            if j['status']=='fechado' and not checked_jobs[-1]['book']['ready']:raise ValueError('Um book fechado do backup está incompleto.')
    memories=payload.get('memories',[]); history=payload.get('memory_history',[])
    if not isinstance(memories,list) or not isinstance(history,list) or len(memories)>10000 or len(history)>50000:
        raise ValueError('Memórias de backup inválidas.')
    def validate_memory(m):
        if not isinstance(m,dict) or not isinstance(m.get('revision'),int) or m['revision']<1:raise ValueError('Revisão de memória inválida.')
        editor=normalize_memory(m.get('editor',{}))
        if m.get('id')!=context_key(editor):raise ValueError('A memória pertence a outra variante.')
        return {**m,'editor':editor}
    memories=[validate_memory(m) for m in memories]
    for e in history:
        if not isinstance(e,dict) or not e.get('id') or not e.get('memory_id'):raise ValueError('Histórico de memória inválido.')
        for k in ('before','after'):
            if e.get(k):
                e[k]=validate_memory(e[k])
                if e[k]['id']!=e['memory_id']:raise ValueError('Histórico pertence a outra variante.')
    conf=clean_settings(payload['settings']) if payload.get('settings') else None
    drafts=payload.get('drafts',[])
    if not isinstance(drafts,list) or len(drafts)>1 or any(not isinstance(d,dict) or d.get('id')!='current' for d in drafts):raise ValueError('Rascunho do backup inválido.')
    work_drafts=payload.get('work_drafts',[])
    if not isinstance(work_drafts,list) or len(work_drafts)>10000 or any(not isinstance(d,dict) or not d.get('draft_id') or d.get('id')!='draft_'+learning.digest(d['draft_id']) for d in work_drafts):raise ValueError('Rascunhos automáticos do backup inválidos.')
    if payload.get('learning'):
        # Validate the whole history in isolation before any restore writes.
        with sqlite3.connect(':memory:') as validation:
            learning.ensure(validation);learning.import_records(validation,payload['learning'])
    custom=payload.get('custom_symbols',[])
    if not isinstance(custom,list) or len(custom)>1000:raise ValueError('Simbologias do backup inválidas.')
    checked_symbols=[];symbol_ids=set()
    for item in custom:
        symbol=clean_symbol(item,draft=True)
        revision=item.get('revision',1)
        if symbol['id'] in symbol_ids or not isinstance(revision,int) or revision<1:raise ValueError('Revisão ou identificador repetido nas simbologias.')
        symbol_ids.add(symbol['id']);symbol.update(revision=revision,updated_at=str(item.get('updated_at',now()))[:80]);checked_symbols.append(symbol)
    backup_database()
    for name,binary in prepared:
        (DATA_DIR/'media').mkdir(exist_ok=True)
        (DATA_DIR/'media'/name).write_bytes(binary)
    # Merge instead of deleting unrelated records. UI asks before replacing matching IDs.
    with connect() as db:
        for table,items in [('profiles',cleaned),('jobs',checked_jobs),('memories',memories),('memory_history',history),('custom_symbols',checked_symbols)]:
            for item in items: db.execute(f'INSERT OR REPLACE INTO {table} VALUES (?,?)',(item['id'],json.dumps(item,ensure_ascii=False)))
        if conf:db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',('config',json.dumps(dict(conf,id='config'),ensure_ascii=False)))
        for item in drafts:db.execute('INSERT OR REPLACE INTO drafts VALUES (?,?)',(item['id'],json.dumps(item,ensure_ascii=False)))
        for item in work_drafts:learning.put(db,'work_drafts',item)
        for item in drafts+work_drafts:
            if item.get('draft_id'):db.execute('DELETE FROM cleared_drafts WHERE id=?',(item['draft_id'],))
        if payload.get('learning'):learning.import_records(db,payload['learning'])
        if not payload.get('learning'):
            for job in sorted(checked_jobs,key=lambda j:j.get('saved_at','')):
                learning.capture(db,{**job,'services':job['result']['services']},'registro importado',historical_time=job.get('saved_at'),record_id='job:'+job['id'])
    result={'profiles':len(cleaned),'jobs':len(checked_jobs)}
    if payload.get('schema') in (2,3,4):result.update(memories=len(memories),memory_history=len(history))
    if payload.get('schema') in (3,4):result.update(media=len(prepared))
    return result

class Handler(BaseHTTPRequestHandler):
    server_version='FechamentoLocal'
    sys_version=''
    def log_message(self,fmt,*args): pass
    def send(self,data,status=200,kind='application/json; charset=utf-8',filename=None):
        if not isinstance(data,bytes): data=json.dumps(data,ensure_ascii=False).encode('utf-8')
        self.send_response(status); self.send_header('Content-Type',kind)
        self.send_header('Content-Length',str(len(data))); self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        ancestors="'self'" if urlparse(self.path).path=='/map_v11.html' else "'none'"
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; worker-src 'self'; style-src 'self' 'unsafe-inline'; font-src 'self' data: blob:; img-src 'self' data: blob: https://server.arcgisonline.com; connect-src 'self'; frame-src 'self'; frame-ancestors "+ancestors+"; base-uri 'none'; form-action 'self'")
        if filename: self.send_header('Content-Disposition',f'attachment; filename="{filename}"')
        self.end_headers();self.wfile.write(data)
    def valid_host(self):
        return self.headers.get('Host','') in {f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}
    def valid_origin(self):
        origin=self.headers.get('Origin')
        return self.headers.get('Sec-Fetch-Site','')!='cross-site' and (
            origin is None or origin=='http://'+self.headers.get('Host',''))
    def do_GET(self):
        if not self.valid_host(): return self.send({'error':'Host inválido.'},403)
        if not self.valid_origin(): return self.send({'error':'Abra o programa diretamente pelo iniciador.'},403)
        path=urlparse(self.path); q=parse_qs(path.query)
        try:
            if path.path=='/api/health': return self.send({'app':APP_ID,'version':VERSION,'instance_id':INSTANCE_ID})
            if path.path=='/api/update-status':return self.send(updates.read_status(DATA_DIR))
            if path.path=='/api/bootstrap': return self.send({'catalog':CATALOG,'profiles':records('profiles'),'token':TOKEN,'bases':base_summaries(),'memories':records('memories'),'equipment_references':BASE_DATA['equipment_references'],'version':VERSION,'network_symbols':symbol_catalog(),'custom_symbols':records('custom_symbols'),'settings':settings(),'draft':next(iter(records('drafts')),None),'patterns':learning_bootstrap(),'cleared_draft_ids':cleared_draft_ids()})
            if path.path=='/api/learning/patterns':
                with connect() as db:return self.send(learning.patterns(db))
            if path.path=='/api/working-drafts':return self.send(records('work_drafts'))
            if path.path in ('/api/learning/export','/api/learning/publish','/api/learning/history'):
                with connect() as db:
                    if path.path.endswith('publish'):return self.send(learning.export_patterns(db),filename='padroes_materiais.json')
                    data=learning.export_records(db)
                    if path.path.endswith('history'):return self.send(sorted(data['events'],key=lambda e:e.get('updated_at',''),reverse=True)[:500])
                    return self.send(data,filename='registros_ajustes_responsaveis.json')
            if path.path=='/api/custom-symbols':return self.send(records('custom_symbols'))
            if path.path=='/api/settings':return self.send(settings())
            if path.path=='/api/records-sync':return self.send(record_sync().status())
            if path.path=='/api/coordinate':
                lat,lon=geo.parse_coord(parse_qs(path.query).get('q',[''])[0])
                return self.send({'lat':lat,'lon':lon,'utm':geo.format_utm(lat,lon)})
            if path.path=='/api/geo':return self.send(geo.search(q.get('q',[''])[0],settings()['radius_m']))
            if path.path=='/api/suggest': return self.send(suggestions(q.get('id',[''])[0]))
            if path.path=='/api/profiles': return self.send(records('profiles'))
            if path.path=='/api/memories': return self.send(records('memories'))
            if path.path=='/api/memory-history': return self.send(records('memory_history'))
            if path.path=='/api/jobs': return self.send(records('jobs'))
            if path.path=='/api/backup':
                return self.send(backup_payload(),filename='backup_fechamento_engelmig.json')
            if path.path in ('/book','/materials-report','/api/summary'):
                jid=q.get('id',[''])[0];job=next((j for j in records('jobs') if j['id']==jid),None)
                if not job:return self.send({'error':'Obra não encontrada.'},404)
                if path.path=='/api/summary':return self.send({'text':summary_text(job),'forms_url':job.get('forms_url',settings()['forms_url'])})
                return self.send(materials_report_html(job) if path.path=='/materials-report' else book_html(job),kind='text/html; charset=utf-8')
            if path.path.startswith('/media/'):
                name=path.path[len('/media/'):]
                if not ASSET_RE.fullmatch(name) or not (DATA_DIR/'media'/name).is_file():return self.send({'error':'Arquivo não encontrado.'},404)
                return self.send((DATA_DIR/'media'/name).read_bytes(),kind={'jpg':'image/jpeg','png':'image/png','webp':'image/webp','pdf':'application/pdf'}[name.rsplit('.',1)[1]])
            if path.path=='/api/export':
                jid=q.get('id',[''])[0]; job=next((j for j in records('jobs') if j['id']==jid),None)
                if not job: return self.send({'error':'Obra não encontrada.'},404)
                return self.send(report_csv(job),kind='text/csv; charset=utf-8',filename='mao_de_obra_e_materiais_'+jid[:8]+'.csv')
            name='index.html' if path.path=='/' else path.path.lstrip('/')
            file=(ROOT/'web'/name).resolve();web=(ROOT/'web').resolve()
            kinds={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.mjs':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.png':'image/png','.jpg':'image/jpeg','.json':'application/json; charset=utf-8','.wasm':'application/wasm','.bcmap':'application/octet-stream','.pfb':'application/octet-stream','.ttf':'font/ttf','.icc':'application/octet-stream'}
            if web not in file.parents or not file.is_file() or file.suffix not in kinds:return self.send({'error':'Não encontrado.'},404)
            return self.send(file.read_bytes(),kind=kinds[file.suffix])
        except (ValueError,KeyError) as exc: self.send({'error':str(exc)},400)
        except Exception as exc:
            ident=diagnostics.record(DATA_DIR,'server_get',exc)
            self.send({'error':'Falha ao ler os dados. Baixe o diagnóstico para suporte. Código: '+ident},500)
    def do_POST(self):
        if not self.valid_host() or not self.valid_origin() or self.headers.get('X-App-Token')!=TOKEN: return self.send({'error':'Recarregue a página para continuar.'},403)
        try:
            size=int(self.headers.get('Content-Length','0'))
            limit=4096 if self.path in ('/api/diagnostics','/api/diagnostics-event') else 300_000_000 if self.path in ('/api/restore','/api/learning/import') else 71_000_000 if self.path=='/api/project-pdf' else 44_000_000 if self.path=='/api/media' else 25_000_000
            if not 0<size<=limit: raise ValueError('Arquivo ou requisição fora do limite permitido.')
            data=json.loads(self.rfile.read(size).decode('utf-8'))
            if not isinstance(data,dict): raise ValueError('Dados inválidos.')
            if self.path=='/api/diagnostics':return self.send(diagnostics.report(DATA_DIR,VERSION),filename='diagnostico_fechamento.json')
            if self.path=='/api/diagnostics-event':
                category,client=diagnostics.client_event(data)
                return self.send({'id':diagnostics.record(DATA_DIR,category,client=client)})
            if self.path=='/api/media':return self.send(put_media(data,DATA_DIR/'media'))
            if self.path=='/api/project-pdf':return self.send(put_pdf(data,DATA_DIR/'media'))
            if self.path=='/api/media-check':
                refs=data.get('refs',[])
                if not isinstance(refs,list) or len(refs)>300 or any(not isinstance(ref,str) or not ASSET_RE.fullmatch(ref) for ref in refs):raise ValueError('Lista de arquivos inválida.')
                present=available_media()
                return self.send({'missing':[ref for ref in refs if ref not in present or (DATA_DIR/'media'/ref).stat().st_size<12]})
            if self.path=='/api/book-check':return self.send(normalize_book(data.get('book'),calculate(data.get('services',[]))['services'],available_media()))
            if self.path=='/api/book-preview':return self.send(preview_book(data))
            if self.path=='/api/job-folder':return self.send(open_job_folder(data))
            if self.path=='/api/draft-clear':return self.send(clear_draft(data))
            if self.path=='/api/draft':
                return self.send(automatic_draft(data))
            if self.path=='/api/learning/select':
                with connect() as db:return self.send(learning.select(db,data))
            if self.path=='/api/learning/import':
                with LEARNING_LOCK,connect() as db:
                    result=learning.import_records(db,data);learning.write_named_exports(db,DATA_DIR,force=True)
                return self.send(result)
            if self.path=='/api/custom-symbols':return self.send(save_symbol(data))
            if self.path=='/api/settings':
                conf=clean_settings(data);save_record('settings',dict(conf,id='config'))
                if SYNC is not None:SYNC.trigger()
                return self.send(conf)
            if self.path=='/api/repository-check':return self.send(updates.repository_status(clean_settings(data)))
            if self.path=='/api/records-sync':return self.send(record_sync().trigger())
            if self.path=='/api/update-check':return self.send(updates.check(ROOT,settings(),VERSION))
            if self.path=='/api/update-notice':return self.send(updates.notice(ROOT,settings(),VERSION,force=data.get('force') is True))
            if self.path=='/api/update-apply':
                backup_database()
                result=updates.apply(ROOT,settings(),VERSION,port=self.server.server_port,data_dir=DATA_DIR)
                if result.get('started'):
                    self.send(result)
                    import time
                    threading.Thread(target=lambda: (time.sleep(.8),self.server.shutdown()),daemon=True).start()
                    return
                return self.send(result)
            if self.path=='/api/calculate': return self.send(calculate(data.get('services',[])))
            if self.path=='/api/base':return self.send(load_base(data))
            if self.path=='/api/confirm-service':
                result=calculate([data.get('service',{})])
                service=result['services'][0]
                if not service['reviewed']:raise ValueError('Confira a composição antes de adicionar.')
                memory=remember(service) if data.get('remember') is True else None
                if data.get('automatic'):
                    with LEARNING_LOCK,connect() as db:
                        learning.capture(db,{**data.get('meta',{}),'editor':service,'editor_touched':True,'editing':data.get('editing',-1)},'serviço adicionado',only_editor=True)
                if memory:service['memory_revision']=memory['revision']
                return self.send({'service':service,'memory':memory})
            if self.path=='/api/remember':return self.send(remember(data))
            if self.path=='/api/forget-memory':return self.send(forget_memory(str(data.get('id',''))))
            if self.path=='/api/recover-memory':return self.send(recover_memory(str(data.get('event_id',''))))
            if self.path=='/api/profile':
                profile=clean_profile(data)
                profile.update(id=str(data.get('id') or uuid.uuid4().hex),updated_at=now())
                save_record('profiles',profile);return self.send(profile)
            if self.path=='/api/job': return self.send(save_job(data))
            if self.path=='/api/restore': return self.send(restore(data))
            return self.send({'error':'Não encontrado.'},404)
        except (ValueError,KeyError,TypeError,AttributeError) as exc: self.send({'error':str(exc)},400)
        except Exception as exc:
            ident=diagnostics.record(DATA_DIR,'server_post',exc)
            self.send({'error':'Não foi possível salvar. Baixe o diagnóstico para suporte. Código: '+ident},500)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8766);parser.add_argument('--no-browser',action='store_true');parser.add_argument('--reuse-port',action='store_true')
    args=parser.parse_args();connect().close()
    server=None
    for port in range(args.port,args.port+(1 if args.reuse_port else 10)):
        try: server=ThreadingHTTPServer(('127.0.0.1',port),Handler);break
        except OSError:
            from urllib.request import urlopen
            try:
                with urlopen(f'http://127.0.0.1:{port}/api/health',timeout=.5) as r: health=json.load(r)
                if health.get('app')==APP_ID:
                    if health.get('version')!=VERSION:
                        raise SystemExit('Feche a janela da versão anterior antes de iniciar a versão '+VERSION+'.')
                    if not args.no_browser:webbrowser.open(f'http://127.0.0.1:{port}')
                    print('O programa já está aberto.');return
            except Exception: pass
    if server is None: raise SystemExit('Não foi possível abrir uma porta local. Feche outras instâncias.')
    url=f'http://127.0.0.1:{server.server_port}'
    print(f'Engelmig - Fechamento de Obras\nAbra {url}\nMantenha esta janela aberta. Ctrl+C para encerrar.\nDados: {DB}',flush=True)
    learning_bootstrap();record_sync().start()
    if not args.no_browser:threading.Timer(.4,lambda:webbrowser.open(url)).start()
    try: server.serve_forever()
    except KeyboardInterrupt: print('\nPrograma encerrado.')
    finally:
        if SYNC is not None:SYNC.stop()
        server.server_close()

if __name__=='__main__': main()
