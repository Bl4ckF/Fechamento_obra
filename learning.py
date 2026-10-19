"""Histórico automático e padrões observados, separados por mão de obra/variante.

Cada registro salvo tem um voto, mesmo quando repete uma composição anterior.
Seu identificador é preservado nas sincronizações para não contar um download
como um novo salvamento.
O padrão usa o conjunto de materiais mais frequente e uma composição real
desse conjunto; não combina quantidades de composições diferentes.
"""
import hashlib
import json
import os
import re
import time
import uuid
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from decimal import Decimal
from engine import ROOT, LABOR, BASES, MATERIALS, clean_service, norm, decimal_text
from compositions import context_key

SCHEMA=1

def stamp():return datetime.now(timezone.utc).isoformat(timespec='microseconds')
def normalized_time(value):
    try:
        when=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        return when.replace(tzinfo=when.tzinfo or timezone.utc).astimezone(timezone.utc).isoformat(timespec='microseconds')
    except (ValueError,TypeError):return '1970-01-01T00:00:00.000000+00:00'
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def dump(value):return json.dumps(value,ensure_ascii=False,separators=(',',':'))
def read_rows(db,table):return [json.loads(r[0]) for r in db.execute(f'SELECT payload FROM {table}')]
def put(db,table,obj):db.execute(f'INSERT OR REPLACE INTO {table} VALUES (?,?)',(obj['id'],dump(obj)))

def ensure(db):
    for table in ('learning_sources','learning_events','learning_meta'):
        db.execute(f'CREATE TABLE IF NOT EXISTS {table} (id TEXT PRIMARY KEY,payload TEXT NOT NULL)')

def annotate(raw):
    raw=deepcopy(raw);labor=LABOR.get(raw.get('labor_id'))
    if labor:
        for key in ('code','operation','scope'):raw.setdefault(key,labor[key])
    for row in raw.get('materials',[]) if isinstance(raw.get('materials',[]),list) else []:
        if isinstance(row,dict) and row.get('material_id') in MATERIALS:row.setdefault('code',MATERIALS[row['material_id']]['code'])
    return raw

def remap_catalog(raw):
    raw=deepcopy(raw)
    if raw.get('code'):
        current=LABOR.get(raw.get('labor_id'))
        matches=lambda l:all(l.get(k)==raw.get(k) for k in ('code','operation','scope') if raw.get(k))
        if not current or not matches(current):
            candidates=[l for l in LABOR.values() if matches(l)]
            if len(candidates)!=1:raise ValueError('A mão de obra mudou no catálogo. Confira sua correspondência antes de reutilizar o padrão.')
            raw['labor_id']=candidates[0]['id']
    for row in raw.get('materials',[]):
        code=row.get('code');current=MATERIALS.get(row.get('material_id'))
        if code and (not current or current['code']!=code):
            candidates=[m for m in MATERIALS.values() if m['code']==code]
            if len(candidates)!=1:raise ValueError('Material '+str(code)+': confira a correspondência no catálogo atualizado.')
            row['material_id']=candidates[0]['id']
    return raw

def eligible(raw,responsible):
    if not str(responsible).strip():return None,'Informe o responsável para identificar a contribuição.'
    try:
        editor=clean_service({**remap_catalog(raw),'quantity':'1','reviewed':False})
        if not editor['materials'] and not editor['no_materials']:raise ValueError('Composição ainda sem materiais.')
        if not editor['code']:raise ValueError('Mão de obra sem código na origem.')
        base=BASES.get(editor['base_id'])
        if base and base['kind']=='transformer' and not editor['context']:
            raise ValueError('Informe a potência/variante complementar do transformador.')
        editor.update(point_id='',entry_id='',note='',memory_revision=None)
        if not editor['variant'].strip():editor['variant']='Padrão'
        # Soma linhas repetidas, mantendo movimento e unidade separados.
        rows={}
        for row in editor['materials']:
            key=(row['material_id'],row['movement'],row['unit'])
            if key not in rows:rows[key]={**row,'coefficient':Decimal(0)}
            rows[key]['coefficient']+=Decimal(row['coefficient'])
        for row in rows.values():row['coefficient']=decimal_text(row['coefficient'])
        editor['materials']=sorted(rows.values(),key=lambda r:(r['material_id'],r['movement'],r['unit']))
        return editor,''
    except (ValueError,KeyError,TypeError,AttributeError) as exc:return None,str(exc)

def capture(db,payload,origin='rascunho',only_editor=False,historical_time=None,record_id=None):
    responsible=str(payload.get('responsible') or '').strip()[:160]
    work_order=str(payload.get('work_order') or '').strip()[:120]
    work=str(payload.get('draft_id') or ('obra:'+norm(work_order)+'|'+str(payload.get('date',''))+'|'+norm(responsible)))[:400]
    items=[] if only_editor else [(s,i,'serviço') for i,s in enumerate(payload.get('services') or [])]
    if isinstance(payload.get('editor'),dict) and payload.get('editor_touched'):
        index=payload.get('editing',-1)
        if not only_editor and isinstance(index,int) and 0<=index<len(items):items[index]=(payload['editor'],index,'editor')
        else:items.append((payload['editor'],index if isinstance(index,int) and index>=0 else 'editor','editor'))
    # Editor e linha aplicada representam o mesmo serviço dentro deste snapshot.
    # Serviços distintos e snapshots repetidos são preservados integralmente.
    unique=[];counts=Counter()
    for raw,index,kind in items:
        if isinstance(raw,dict):
            entry=str(raw.get('entry_id') or index);count=counts[entry];counts[entry]+=1
            unique.append((raw,entry+('#repetido'+str(count) if count else ''),kind))
    items=unique;active_ids={digest([work,entry]) for raw,entry,_ in items}
    changed=0;pending=[];batch=str(record_id or payload.get('record_id') or uuid.uuid4().hex)[:200]
    for raw,entry,kind in items:
        if not isinstance(raw,dict):continue
        raw=annotate(raw)
        ident=digest([work,entry])
        editor,reason=eligible(raw,responsible)
        fingerprint=digest([raw,responsible,work_order])
        old=db.execute('SELECT payload FROM learning_sources WHERE id=?',(ident,)).fetchone()
        old=json.loads(old[0]) if old else None
        when=normalized_time(historical_time) if historical_time else stamp()
        row={'id':ident,'work_id':work,'responsible':responsible,'work_order':work_order,'updated_at':when,
             'origin':origin,'kind':kind,'raw':raw,'editor':editor,'reason':reason,'fingerprint':fingerprint}
        event={**row,'id':digest(['registro-v5',batch,ident]),'source_id':ident,'record_id':batch}
        if db.execute('SELECT 1 FROM learning_events WHERE id=?',(event['id'],)).fetchone():continue
        if not old or normalized_time(old.get('updated_at'))<=when:put(db,'learning_sources',row)
        put(db,'learning_events',event)
        actor=digest(norm(responsible))
        put(db,'learning_meta',{'id':'dirty_'+actor,'responsible':responsible})
        changed+=1
        if reason:pending.append(reason)
    if not only_editor and isinstance(payload.get('services'),list) and origin=='rascunho':
        for old in read_rows(db,'learning_sources'):
            if old.get('work_id')!=work or old.get('kind')!='serviço' or old['id'] in active_ids or old.get('inactive'):continue
            removed={**old,'editor':None,'inactive':True,'reason':'Serviço removido do rascunho.','updated_at':stamp(),'fingerprint':digest([old['fingerprint'],'removed'])}
            put(db,'learning_sources',removed)
            put(db,'learning_events',{**removed,'id':digest([removed['id'],removed['updated_at']]),'source_id':removed['id']})
            name=removed.get('responsible','');put(db,'learning_meta',{'id':'dirty_'+digest(norm(name)),'responsible':name});changed+=1
    return {'changed':changed,'pending':list(dict.fromkeys(pending))}

def backfill(db,jobs,memories):
    if db.execute("SELECT 1 FROM learning_meta WHERE id='backfill_v5'").fetchone():return
    for job in sorted(jobs,key=lambda j:j.get('saved_at','')):
        capture(db,{**job,'services':job.get('result',{}).get('services',[])},'registro anterior',historical_time=job.get('saved_at'),record_id='job:'+str(job['id']))
    # As memórias legadas continuam disponíveis na interface; não são
    # transformadas em ocorrências de serviço sem um registro de uso.
    put(db,'learning_meta',{'id':'backfill_v5','updated_at':stamp()})

def write_named_exports(db,folder,force=False):
    state=db.execute("SELECT payload FROM learning_meta WHERE id='export_clock'").fetchone()
    last=json.loads(state[0]).get('time',0) if state else 0
    if not force and time.time()-last<30:return
    dirty=[r for r in read_rows(db,'learning_meta') if r['id'].startswith('dirty_')]
    if not dirty and not force:return
    target=Path(folder)/'registros_responsaveis';target.mkdir(parents=True,exist_ok=True)
    events=read_rows(db,'learning_events')
    for actor in dirty:
        name=actor['responsible'];key=norm(name)
        selected=sorted([e for e in events if norm(e.get('responsible',''))==key],key=lambda e:e['updated_at'])
        slug=re.sub('[^a-z0-9_-]+','_',norm(name).lower()).strip('_')[:55] or 'responsavel_nao_informado'
        path=target/(slug+'_'+digest(key)[:8]+'.json')
        temp=path.with_suffix('.tmp')
        temp.write_text(dump({'schema':SCHEMA,'kind':'registros_responsavel','responsible':name,'exported_at':stamp(),'events':selected}),encoding='utf-8')
        os.replace(temp,path)
        db.execute('DELETE FROM learning_meta WHERE id=?',(actor['id'],))
    put(db,'learning_meta',{'id':'export_clock','time':time.time()})
    path=Path(folder)/'padroes_aprendidos.json';temp=path.with_suffix('.tmp')
    temp.write_text(dump(export_patterns(db)),encoding='utf-8');os.replace(temp,path)

def bundled_samples():
    path=ROOT/'data/padroes_materiais.json'
    if not path.exists():return []
    data=json.loads(path.read_text(encoding='utf-8'))
    if data.get('kind')!='padroes_materiais' or data.get('schema')!=SCHEMA:raise ValueError('Base de padrões incompatível.')
    return validate_samples(data.get('samples',[]))

def validate_samples(samples):
    if not isinstance(samples,list) or len(samples)>100000:raise ValueError('Base de padrões fora do limite.')
    out=[]
    for item in samples:
        if not isinstance(item,dict) or not re.fullmatch('[a-f0-9]{64}',str(item.get('id',''))):raise ValueError('Identificador do padrão inválido.')
        editor=None
        if item.get('editor'):
            editor,reason=eligible(item['editor'],'Base compartilhada')
            if not editor:raise ValueError('Composição inválida na base: '+reason)
        out.append({'id':item['id'],'updated_at':normalized_time(item.get('updated_at')),'editor':editor,'shared':True})
    return out

def merged_sources(db):
    combined={r['id']:r for r in bundled_samples()}
    events=read_rows(db,'learning_events')
    represented={r.get('source_id') for r in events}
    for source in represented:combined.pop(source,None)
    rows=[r for r in read_rows(db,'learning_sources') if r['id'] not in represented]+events
    for row in rows:
        if row.get('editor'):
            row['editor'],row['reason']=eligible(row['editor'],row.get('responsible') or 'Base preservada')
        old=combined.get(row['id'])
        if not old or row.get('updated_at','')>=old.get('updated_at',''):combined[row['id']]=row
    return list(combined.values())

def composition_signature(editor,quantities=False):
    return dump([editor['no_materials'],[(r['material_id'],r['movement'],r['unit'],r['coefficient'] if quantities else '') for r in editor['materials']]])

def patterns_from(sources):
    groups=defaultdict(list)
    for row in sources:
        if row.get('editor'):groups[context_key(row['editor'])].append(row)
    patterns=[]
    for key,rows in groups.items():
        members_by_set=defaultdict(list)
        for row in rows:members_by_set[composition_signature(row['editor'])].append(row)
        sets={signature:len(members) for signature,members in members_by_set.items()}
        chosen_set=max(sets,key=lambda signature:(sets[signature],max(r['updated_at'] for r in members_by_set[signature])))
        members=members_by_set[chosen_set]
        variants=Counter(composition_signature(r['editor'],True) for r in members)
        winner=max(members,key=lambda r:(variants[composition_signature(r['editor'],True)],r['updated_at']))
        editor=deepcopy(winner['editor']);freq={}
        for row in rows:
            for material in row['editor']['materials']:
                mid=(material['material_id'],material['movement'],material['unit'])
                if mid not in freq:freq[mid]={**material,'occurrences':0,'quantities':Counter()}
                freq[mid]['occurrences']+=1;freq[mid]['quantities'][material['coefficient']]+=1
        for material in freq.values():
            material['frequency']=round(100*material['occurrences']/len(rows),1)
            material['quantities']=dict(material['quantities'])
        support=sets[chosen_set]
        patterns.append({'id':key,'editor':editor,'uses':len(rows),'support':support,'confidence':round(100*support/len(rows),1),
            'auto_apply':support>len(rows)/2,'different_sets':len(sets),'quantity_variations':len(variants),
            'responsibles':len({norm(r.get('responsible','')) for r in rows if r.get('responsible')}),
            'updated_at':max(r['updated_at'] for r in rows),'materials_frequency':list(freq.values())})
    return sorted(patterns,key=lambda p:(p['editor']['code'],p['editor']['variant'],p['id']))

def patterns(db):return patterns_from(merged_sources(db))

def select(db,query):
    options=[p for p in patterns(db) if p['editor']['labor_id']==query.get('labor_id')]
    exact=bool(query.get('base_id') or query.get('variant') or query.get('context'))
    if exact:
        key=context_key(query);options=[p for p in options if p['id']==key]
    personal=[]
    for row in read_rows(db,'learning_sources'):
        if not row.get('editor') or norm(row.get('responsible',''))!=norm(query.get('responsible','')):continue
        row['editor'],_=eligible(row['editor'],row.get('responsible') or 'Base preservada')
        if row['editor'] and row['editor']['labor_id']==query.get('labor_id'):personal.append(row)
    if exact:personal=[r for r in personal if context_key(r['editor'])==context_key(query)]
    chosen=None;source=''
    keys={context_key(r['editor']) for r in personal}
    if query.get('responsible','').strip() and len(keys)==1:
        chosen=max(personal,key=lambda r:r['updated_at'])['editor'];source='Seu último ajuste automático'
    elif len(options)==1 and options[0]['auto_apply']:
        chosen=options[0]['editor'];source=f"Padrão observado em {options[0]['support']} de {options[0]['uses']} registros"
    return {'editor':deepcopy(chosen),'source':source,'options':options}

def export_records(db):
    return {'schema':SCHEMA,'kind':'registros_ajustes','sampling':'saved_records_v5','exported_at':stamp(),'sources':read_rows(db,'learning_sources'),'events':read_rows(db,'learning_events')}

def sync_events(db):
    """Somente composições, responsável e data; book e credenciais ficam locais."""
    out=[]
    allowed={'labor_id','code','operation','scope','quantity','variant','context','base_id','base_mode','no_materials','reviewed','materials'}
    for event in read_rows(db,'learning_events'):
        raw={k:v for k,v in event.get('raw',{}).items() if k in allowed}
        out.append({k:v for k,v in {**event,'raw':raw}.items() if k in
            {'id','source_id','record_id','responsible','updated_at','origin','kind','raw','inactive'}})
    return out

def export_patterns(db):
    samples=[{'id':r['id'],'updated_at':r.get('updated_at',''),'editor':r.get('editor')} for r in merged_sources(db)]
    return {'schema':SCHEMA,'kind':'padroes_materiais','exported_at':stamp(),'samples':samples,'patterns':patterns_from(samples)}

def import_records(db,data):
    if not isinstance(data,dict) or data.get('schema')!=SCHEMA:raise ValueError('Arquivo de aprendizado incompatível.')
    kind=data.get('kind');rows=[];events=[]
    if kind=='padroes_materiais':rows=validate_samples(data.get('samples',[]))
    elif kind in ('registros_ajustes','registros_responsavel'):
        events=data.get('events',[])
        if not isinstance(events,list) or len(events)>100000:raise ValueError('Histórico de ajustes inválido.')
        rows=data.get('sources',[])
        if not isinstance(rows,list) or len(rows)>100000:raise ValueError('Registros inválidos.')
        if events:
            latest={}
            for event in events:
                if not isinstance(event,dict):raise ValueError('Histórico de ajustes inválido.')
                sid=event.get('source_id')
                if sid and (sid not in latest or event.get('updated_at','')>latest[sid].get('updated_at','')):latest[sid]={**event,'id':sid}
            rows=rows+list(latest.values())
        for row in rows+events:
            if not isinstance(row,dict) or not re.fullmatch('[a-f0-9]{64}',str(row.get('id',''))):raise ValueError('Registro de ajuste inválido.')
            if row.get('shared') and 'raw' not in row:
                row.update(validate_samples([row])[0]);continue
            if not isinstance(row.get('raw'),dict):raise ValueError('Conteúdo de ajuste inválido.')
            row['responsible']=str(row.get('responsible',''))[:160]
            row['editor'],row['reason']=eligible(row['raw'],row['responsible'] or ('Memória anterior' if row.get('legacy') else ''))
            if row.get('inactive'):row['editor']=None;row['reason']='Serviço removido do rascunho.'
            row['updated_at']=normalized_time(row.get('updated_at'))
    else:raise ValueError('Escolha um arquivo de registros ou padrões do programa.')
    changed=0
    for row in rows:
        old=db.execute('SELECT payload FROM learning_sources WHERE id=?',(row['id'],)).fetchone()
        if old and json.loads(old[0]).get('updated_at','')>=row.get('updated_at',''):continue
        put(db,'learning_sources',row);changed+=1
    imported_events=0
    for event in events:
        imported_events+=db.execute('INSERT OR IGNORE INTO learning_events VALUES (?,?)',(event['id'],dump(event))).rowcount
        name=event.get('responsible','');put(db,'learning_meta',{'id':'dirty_'+digest(norm(name)),'responsible':name})
    return {'imported':changed,'imported_events':imported_events,'patterns':len(patterns(db))}
