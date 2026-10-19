"""Documento vetorial local para reabrir e editar o croqui."""
from symbols import clean_symbol
import math
import re
import json
from pathlib import Path
from functools import lru_cache

@lru_cache(maxsize=1)
def symbol_catalog():
    return json.loads((Path(__file__).parent/'data/simbolos_rede.json').read_text(encoding='utf-8'))


def clean_drawing(data,available=None):
    if data is None:return None
    from book import photo_ref, pdf_ref
    if not isinstance(data,dict) or data.get('version')!=1:raise ValueError('Desenho do croqui inválido.')
    objects=data.get('objects',[])
    if not isinstance(objects,list) or len(objects)>1000:raise ValueError('Limite de 1.000 objetos no croqui.')
    def number(value,low,high):
        try:n=float(value)
        except (ValueError,TypeError):raise ValueError('Coordenada do desenho inválida.')
        if not math.isfinite(n) or not low<=n<=high:raise ValueError('Valor fora da área de desenho.')
        return round(n,3)
    out={'version':1,'width':1200,'height':800,'objects':[],'background_ref':None}
    if data.get('background_ref'):out['background_ref']=photo_ref(data['background_ref'],available)
    source=data.get('background_source')
    if source and out['background_ref']:
        if not isinstance(source,dict):raise ValueError('Origem do fundo do croqui inválida.')
        out['background_source']={'kind':'pdf' if source.get('kind')=='pdf' else 'image','name':str(source.get('name',''))[:200]}
        if source.get('kind')=='pdf':
            out['background_source']['page']=int(number(source.get('page',1),1,100000))
            out['background_source']['rotation']=int(number(source.get('rotation',0),0,270))
            for key in ('page_width','page_height'):
                if source.get(key) is not None:out['background_source'][key]=number(source[key],1,100000)
    def text_style(obj):
        font=obj.get('font','Arial')
        if font not in ('Arial','Times New Roman','Courier New'):raise ValueError('Fonte do croqui inválida.')
        return {'text':str(obj.get('text',''))[:2000],'size':number(obj.get('size',22),2,160),
                'rotation':number(obj.get('rotation',0),-360,360),'font':font,
                'bold':obj.get('bold') is True,'italic':obj.get('italic') is True}
    pdf_texts=data.get('pdf_texts') or []
    if not isinstance(pdf_texts,list) or len(pdf_texts)>3000:raise ValueError('Limite de 3.000 textos reconhecidos por página.')
    pdf_ids=set()
    if pdf_texts:
        if not out['background_ref'] or not source or source.get('kind')!='pdf':raise ValueError('Os textos precisam de uma página PDF como fundo.')
        out['pdf_text_background_ref']=photo_ref(data.get('pdf_text_background_ref'),available)
        out['pdf_texts']=[]
        for item in pdf_texts:
            if not isinstance(item,dict):raise ValueError('Texto do PDF inválido.')
            ident=str(item.get('id',''))
            if not re.fullmatch(r'pdf_[0-9]{1,5}',ident) or ident in pdf_ids:raise ValueError('Identificador de texto PDF inválido ou repetido.')
            pdf_ids.add(ident)
            box=item.get('box')
            if not isinstance(box,dict):raise ValueError('Área do texto PDF inválida.')
            bounds={k:number(box.get(k),0,1200 if k in ('x','w') else 800) for k in ('x','y','w','h')}
            if bounds['w']<=0 or bounds['h']<=0 or bounds['x']+bounds['w']>1200.01 or bounds['y']+bounds['h']>800.01:raise ValueError('Texto fora da área do PDF.')
            color=str(item.get('color','#111111'))
            if not re.fullmatch('#[0-9a-fA-F]{6}',color):raise ValueError('Cor do texto PDF inválida.')
            out['pdf_texts'].append(dict(text_style(item),id=ident,x1=number(item.get('x1'),0,1200),y1=number(item.get('y1'),0,800),
                text_width=number(item.get('text_width',0),0,10000),box=bounds,color=color))
    vertices=0
    def line_geometry(obj):
        nonlocal vertices
        row={}
        if obj.get('type')=='line':
            row={k:number(obj.get(k),0,1200 if k.startswith('x') else 800) for k in ('x1','y1','x2','y2')}
        elif obj.get('type')=='path':
            commands=obj.get('commands',[])
            if not isinstance(commands,list) or not 2<=len(commands)<=2000:raise ValueError('Traçado vetorial inválido.')
            clean=[]
            for command in commands:
                if not isinstance(command,list) or not command or command[0] not in ('M','L','C','Q','Z') or len(command)!={'M':3,'L':3,'C':7,'Q':5,'Z':1}[command[0]]:raise ValueError('Comando de linha inválido.')
                clean.append([command[0]]+[number(value,0,1200 if i%2==0 else 800) for i,value in enumerate(command[1:])])
                vertices+=(len(command)-1)//2
            if clean[0][0]!='M' or vertices>150000:raise ValueError('Geometria ou quantidade de pontos de linha inválida.')
            row['commands']=clean
        else:raise ValueError('Tipo de linha inválido.')
        row.update(label=str(obj.get('label',''))[:96],line_cap=obj.get('line_cap') if obj.get('line_cap') in ('butt','round','square') else 'round',line_join=obj.get('line_join') if obj.get('line_join') in ('miter','round','bevel') else 'round')
        if obj.get('dash_array'):
            values=obj['dash_array']
            if not isinstance(values,list) or not 1<=len(values)<=32:raise ValueError('Tracejado inválido.')
            row['dash_array']=[number(v,0,1000) for v in values]
            if not sum(row['dash_array']):raise ValueError('Tracejado vazio.')
            row['dash_offset']=number(obj.get('dash_offset',0),-1000,1000)
        return row
    pdf_lines=data.get('pdf_lines') or []
    if not isinstance(pdf_lines,list) or len(pdf_lines)>5000:raise ValueError('Limite de 5.000 traços reconhecidos por página.')
    line_ids=set()
    if pdf_lines:
        if not out['background_ref'] or not source or source.get('kind')!='pdf':raise ValueError('As linhas precisam de uma página PDF como fundo.')
        out['pdf_source_ref']=pdf_ref(data.get('pdf_source_ref'),available);out['pdf_lines']=[]
        for line in pdf_lines:
            if not isinstance(line,dict):raise ValueError('Linha do PDF inválida.')
            ident=str(line.get('id',''));index=int(number(line.get('operator_index'),0,10000000))
            if ident!='pdfline_'+str(index) or ident in line_ids:raise ValueError('Identificador de linha PDF inválido ou repetido.')
            line_ids.add(ident);color=str(line.get('color','#000000'))
            if not re.fullmatch('#[0-9a-fA-F]{6}',color):raise ValueError('Cor da linha inválida.')
            row=dict(line_geometry(line),id=ident,type=line['type'],operator_index=index,color=color,width=number(line.get('width',1),.1,30),dash=line.get('dash') if line.get('dash') in ('solid','dashed','dotted') else 'solid',arrow='none')
            out['pdf_lines'].append(row)
    identifiers=set()
    for obj in objects:
        if not isinstance(obj,dict) or obj.get('type') not in ('line','path','pen','rect','ellipse','text','symbol'):raise ValueError('Objeto de croqui inválido.')
        ident=str(obj.get('id',''))[:80]
        if not re.fullmatch('[a-zA-Z0-9_-]+',ident) or ident in identifiers:raise ValueError('Identificador do desenho inválido.')
        identifiers.add(ident)
        color=str(obj.get('color','#183e53'))
        if not re.fullmatch('#[0-9a-fA-F]{6}',color):raise ValueError('Cor do desenho inválida.')
        row={'id':ident,'type':obj['type'],'color':color,'width':number(obj.get('width',3),.1,30),
             'dash':obj.get('dash') if obj.get('dash') in ('solid','dashed','dotted') else 'solid',
             'arrow':obj.get('arrow') if obj.get('arrow') in ('none','end','both') else 'none'}
        if row['type'] in ('line','path'):
            row.update(line_geometry(obj))
        elif row['type']=='pen':
            points=obj.get('points',[])
            if not isinstance(points,list) or not 1<=len(points)<=5000:raise ValueError('Traço do croqui inválido.')
            vertices+=len(points)
            if vertices>100000:raise ValueError('O croqui excedeu o limite de pontos de desenho.')
            row['points']=[{'x':number(p['x'],0,1200),'y':number(p['y'],0,800)} for p in points]
        else:
            row.update(x1=number(obj.get('x1'),0,1200),y1=number(obj.get('y1'),0,800))
            if row['type']=='symbol':
                symbol_id=str(obj.get('symbol_id',''))
                if obj.get('symbol_definition') is not None:
                    definition=clean_symbol(obj['symbol_definition'])
                    if definition['id']!=symbol_id:raise ValueError('Definição da simbologia não corresponde ao objeto.')
                    row['symbol_definition']=definition
                elif symbol_id not in {s['id'] for s in symbol_catalog()['symbols']}:raise ValueError('Símbolo fora da biblioteca de rede.')
                status=obj.get('status','instalar')
                if status not in ('existente','instalar','retirar'):raise ValueError('Situação do símbolo inválida.')
                row.update(symbol_id=symbol_id,size=number(obj.get('size',70),7,700),
                           rotation=number(obj.get('rotation',0),-360,360),status=status,
                           label=str(obj.get('label',''))[:96],opaque=obj.get('opaque') is True)
            elif row['type']=='text':
                row.update(text_style(obj))
                if obj.get('text_width') is not None:row['text_width']=number(obj['text_width'],0,10000)
            else:row.update(x2=number(obj.get('x2'),0,1200),y2=number(obj.get('y2'),0,800))
        if obj.get('pdf_text_id'):
            if row['type']!='text' or obj['pdf_text_id'] not in pdf_ids or ident!=obj['pdf_text_id']:raise ValueError('Substituição de texto PDF inválida.')
            row['pdf_text_id']=ident
        elif ident in pdf_ids:raise ValueError('Identificador reservado a um texto PDF.')
        if obj.get('pdf_line_id'):
            if row['type'] not in ('line','path') or obj['pdf_line_id'] not in line_ids or ident!=obj['pdf_line_id']:raise ValueError('Substituição de linha PDF inválida.')
            row['pdf_line_id']=ident;row['deleted']=obj.get('deleted') is True
        elif ident in line_ids:raise ValueError('Identificador reservado a uma linha PDF.')
        out['objects'].append(row)
    return out
