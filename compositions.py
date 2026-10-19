"""Composições de origem e memória explícita de ajustes por variante."""
import hashlib
import json
from copy import deepcopy
from decimal import Decimal
from engine import BASE_DATA, BASES, LABOR, MATERIALS, clean_service, calculate, norm

def context_key(data):
    labor_id=data.get('labor_id')
    if labor_id not in LABOR:raise ValueError('Mão de obra não encontrada.')
    base_id=str(data.get('base_id',''))
    if base_id and base_id not in BASES:raise ValueError('Base não encontrada.')
    mode=str(data.get('base_mode') or 'manual')
    context=norm(str(data.get('context','')).strip())
    if not base_id:context=norm(str(data.get('variant') or 'Padrão').strip())
    key=json.dumps([labor_id,base_id,mode,context],ensure_ascii=False,separators=(',',':'))
    return 'mem_'+hashlib.sha256(key.encode()).hexdigest()[:32]

def base_editor(data):
    labor=LABOR.get(data.get('labor_id'))
    base=BASES.get(data.get('base_id'))
    if not labor or not base:raise ValueError('Selecione a mão de obra e uma composição da base.')
    mode=data.get('base_mode','planilha')
    allowed=('instalado','desativado') if base['kind']=='structure' else ('planilha','instalado','desativado')
    if mode not in allowed:raise ValueError('Escolha a movimentação da composição.')
    context=str(data.get('context','')).strip()[:160]
    rows=[]
    for source in base['rows']:
        row=deepcopy(source)
        if base['kind']=='structure':row['movement']=mode
        elif mode!='planilha' and row['movement']!=mode:continue
        row['description']=MATERIALS[row['material_id']]['description']
        rows.append(row)
    warnings=list(base['warnings'])
    if base['kind']=='transformer':
        warnings.append('INST. e DESAT. são colunas independentes da planilha. O filtro não transforma instalação em retirada. O equipamento principal e o elo devem ser conferidos à parte.')
    if 'CONCRETO' in norm(labor['description']) and any('CRUZETA' in norm(r['description']) and 'PRFV' in norm(r['description']) for r in rows):
        warnings.append('Esta mão de obra menciona concreto, mas a base selecionada inclui cruzeta PRFV. Ajuste o material ou a mão de obra antes da conferência.')
    editor={'labor_id':labor['id'],'quantity':'1','variant':base['title']+(' · '+context if context else ''),'note':'',
            'materials':rows,'reviewed':False,'no_materials':False,'base_id':base['id'],'base_mode':mode,'context':context,
            'source_hash':BASE_DATA['source_sha256'],'memory_revision':None}
    return {'editor':editor,'warnings':warnings,'base':base}

def normalize_memory(data):
    editor=clean_service({**data,'quantity':'1'})
    editor['point_id']='';editor['entry_id']=''
    if not editor['reviewed']:raise ValueError('Confira a composição antes de lembrar os ajustes.')
    pending=calculate([editor])['pending']
    if pending:raise ValueError('Resolva antes de lembrar: '+' '.join(pending))
    base=BASES.get(editor['base_id'])
    if base and base['kind']=='transformer' and not editor['context']:
        raise ValueError('Informe a variante complementar do transformador (ex.: 75 kVA) para lembrar sem misturar modelos.')
    if not editor['variant'].strip():editor['variant']='Padrão'
    return editor

def rows_summary(rows):
    out={}
    for r in rows:
        m=MATERIALS[r['material_id']];key=(r['material_id'],r['movement'])
        if key not in out:out[key]={'code':m['code'],'description':m['description'],'movement':r['movement'],'unit':r['unit'],'quantity':Decimal(0)}
        out[key]['quantity']+=Decimal(str(r['coefficient']).replace(',','.'))
    for row in out.values():row['quantity']=str(row['quantity'])
    return out

def difference(before,after):
    a=rows_summary(before);b=rows_summary(after)
    added=[b[k] for k in b.keys()-a.keys()]
    removed=[a[k] for k in a.keys()-b.keys()]
    changed=[{'before':a[k],'after':b[k]} for k in a.keys()&b.keys() if Decimal(a[k]['quantity'])!=Decimal(b[k]['quantity']) or a[k]['unit']!=b[k]['unit']]
    return {'added':sorted(added,key=lambda r:r['code']),'removed':sorted(removed,key=lambda r:r['code']),'changed':sorted(changed,key=lambda r:r['after']['code'])}

def source_diff(editor):
    baseline=base_editor(editor)['editor']['materials'] if editor.get('base_id') else []
    return difference(baseline,editor['materials'])

def memory_payload(data,previous=None):
    editor=normalize_memory(data)
    key=context_key(editor)
    last=previous.get('editor') if previous else None
    same=last is not None and not any(difference(last['materials'],editor['materials']).values()) and all(last.get(k)==editor.get(k) for k in ('no_materials','note','variant','context'))
    if same:return previous,False
    revision=(previous.get('revision',0) if previous else 0)+1
    editor['memory_revision']=revision
    return {'id':key,'revision':revision,'editor':editor,'difference':source_diff(editor),'change':difference(last['materials'] if last else [],editor['materials']),
            'source_hash':BASE_DATA['source_sha256']},True

def base_summaries():
    return [{k:v[k] for k in ('id','kind','params','title','sheet','warnings')}|{'items':len(v['rows'])} for v in BASES.values()]
