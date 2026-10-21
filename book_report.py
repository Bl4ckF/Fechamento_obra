"""Book A4: layout fotográfico do modelo fornecido + páginas específicas."""
from html import escape
from urllib.parse import quote
from decimal import Decimal
import textwrap
import unicodedata
from geo import coordinate_for_book
from engine import LABOR, structure_description
from pricing import service_price, line_total, money

# Os créditos do desenvolvedor aparecem somente na interface do aplicativo.

def e(x):return escape(str(x or ''),quote=True)
def n(x):return format(Decimal(str(x)),'f').replace('.',',')
def chunks(items,size):return [items[i:i+size] for i in range(0,len(items),size)]
def short(value,limit):
    value=' '.join(str(value or '').split())
    return value if len(value)<=limit else value[:limit-1]+'…'
def wrap_text(value,limit=950):
    lines=[]
    for line in str(value or '').splitlines():
        lines.extend(textwrap.wrap(line,width=85,replace_whitespace=False) or [''])
    return ['\n'.join(group) for group in chunks(lines,min(32,max(1,limit//85)))]

def table_groups(rows,cells,widths,budget=185):
    """Conservative A4 row budget including wrapped text and cell padding."""
    groups=[];group=[];height=0
    for row in rows:
        lines=max(sum(max(1,len(textwrap.wrap(line,width=w))) for line in str(value).split('\n')) for value,w in zip(cells(row),widths))
        cost=4.2*lines+4.5
        if group and height+cost>budget:groups.append(group);group=[];height=0
        group.append(row);height+=cost
    if group:groups.append(group)
    return groups

# Larguras aproximadas de Arial/Helvetica em 1/1000 em; sem dependência externa.
PHOTO_WIDTHS = {' ': 278, '!': 278, '"': 355, '#': 556, '$': 556, '%': 889, '&': 667, "'": 191, '(': 333, ')': 333, '*': 389, '+': 584, ',': 278, '-': 333, '.': 278, '/': 278, '0': 556, '1': 556, '2': 556, '3': 556, '4': 556, '5': 556, '6': 556, '7': 556, '8': 556, '9': 556, ':': 278, ';': 278, '<': 584, '=': 584, '>': 584, '?': 556, '@': 1015, 'A': 667, 'B': 667, 'C': 722, 'D': 722, 'E': 667, 'F': 611, 'G': 778, 'H': 722, 'I': 278, 'J': 500, 'K': 667, 'L': 556, 'M': 833, 'N': 722, 'O': 778, 'P': 667, 'Q': 778, 'R': 722, 'S': 667, 'T': 611, 'U': 722, 'V': 667, 'W': 944, 'X': 667, 'Y': 667, 'Z': 611, '[': 278, '\\': 278, ']': 278, '^': 469, '_': 556, '`': 333, 'a': 556, 'b': 556, 'c': 500, 'd': 556, 'e': 556, 'f': 278, 'g': 556, 'h': 556, 'i': 222, 'j': 222, 'k': 500, 'l': 222, 'm': 833, 'n': 556, 'o': 556, 'p': 556, 'q': 556, 'r': 333, 's': 500, 't': 278, 'u': 556, 'v': 500, 'w': 722, 'x': 500, 'y': 500, 'z': 500, '{': 334, '|': 260, '}': 334, '~': 584}
def photo_lines(value,width=132):
    def measure(text):
        simple=''.join(c for c in unicodedata.normalize('NFD',text) if not unicodedata.combining(c))
        return sum(PHOTO_WIDTHS.get(c,700) for c in simple)*8/1000
    result=[]
    for paragraph in str(value or '').splitlines():
        line=''
        for word in paragraph.split():
            trial=(line+' '+word).strip()
            if measure(trial)<=width:line=trial;continue
            if line:result.append(line);line=''
            while measure(word)>width:
                cut=1
                while cut<len(word) and measure(word[:cut+1])<=width:cut+=1
                result.append(word[:cut]);word=word[cut:]
            line=word
        result.append(line)
    return result or ['']

def photo_parts(blocks,budget=21):
    parts=[];part=[];used=0
    for heading,value in blocks:
        lines=photo_lines(value);continued=False
        while lines:
            room=budget-used-2
            if room<1:
                parts.append(part);part=[];used=0;room=budget-2
            taken=lines[:room];lines=lines[room:]
            part.append((heading+(' · continuação' if continued else ''),'\n'.join(taken)))
            used+=2+len(taken);continued=True
            if lines:parts.append(part);part=[];used=0
    if part:parts.append(part)
    return parts or [[]]

def book_html(job,preview=False):
    book=job.get('book') or {};points=book.get('points',[]);pages=[]
    services=job['result'].get('services',[])
    def labor(point_id,operation):return [s for s in services if s.get('point_id')==point_id and s.get('operation')==operation]
    names={p['id']:p['number'] for p in points}
    def header(title='BOOK FOTOGRÁFICO'):
        return f'<header class="book-heading"><img src="/assets/engelmig.png" alt="Engelmig"><div><h1>{e(title)}</h1><strong>OBRA – {e(short(job["work_order"],40))}</strong><p>PRESTADOR: ENGELMIG ELÉTRICA LTDA</p></div><img src="/assets/energisa.png" alt="Energisa"></header><div class="book-meta">Data: {e(short(job.get("date"),20))} · Responsável: {e(short(job.get("responsible"),60))}<br>Local: {e(short(job.get("location"),100))}</div>'
    def add(body,title='BOOK FOTOGRÁFICO',klass=''):
        pages.append((header(title)+body,klass))
    def observation_parts(p,photo):
        blocks=[]
        for operation,label,key in [('INSTALAR','INSTALADO','installed'),('RETIRAR','DESATIVADO','removed')]:
            values='; '.join(structure_description(row) for row in labor(p['id'],operation)) or 'Sem lançamento de mão de obra.'
            if p.get(key):values+='\nObservações: '+p[key]
            blocks.append((label,values))
        if p.get('notes'):blocks.append(('OBSERVAÇÕES',p['notes']))
        equipment='\n'.join(label+': '+p[key] for label,key in [('Patrimônio','patrimony'),('Série','serial'),('Tensão','voltage'),('Potência','power'),('Impedância','impedance'),('Fabricante','manufacturer'),('Data de fabricação','manufactured')] if p.get(key))
        if equipment:blocks.append(('EQUIPAMENTO',equipment))
        if photo.get('caption'):blocks.append(('LEGENDA DA FOTO',photo['caption']))
        return photo_parts(blocks)
    croquis=book.get('croqui_pages')
    if croquis is None:croquis=[{'croqui':book['croqui']}] if book.get('croqui') else []
    if not croquis:add('<h2>Croqui da obra</h2><p>Croqui não informado.</p>','CROQUI DA OBRA')
    for page_number,page in enumerate(croquis,1):
        croqui=page.get('croqui');label=f'Croqui da obra · {page_number}/{len(croquis)}'
        add('<h2>'+label+'</h2>'+ (f'<div class="croqui"><img src="/media/{quote(croqui["ref"])}" alt="Croqui da obra, página {page_number}"></div><p class="pre">{e(croqui.get("caption","")[:240])}</p>' if croqui else '<p>Croqui não informado.</p>'),'CROQUI DA OBRA')
        if croqui and len(croqui.get('caption',''))>240:
            for part in wrap_text(croqui['caption'][240:],1800):add('<h2>Observações do croqui '+str(page_number)+' · continuação</h2><p class="pre">'+e(part)+'</p>','CROQUI DA OBRA')
    if not points:add('<p>Nenhum ponto cadastrado neste registro.</p>')
    for p in points:
        photos=p.get('photos',[]) or [{'ref':'','stage':'Sem foto','caption':''}]
        cards=[]
        for photo in photos:
            parts=observation_parts(p,photo)
            for part_number,part in enumerate(parts,1):cards.append((photo,part,part_number,len(parts)))
        for group in chunks(cards,2):
            body='<div class="photo-head"><span>FOTO</span><span>OBSERVAÇÕES</span></div><div class="photo-grid">'
            for photo,part,part_number,total_parts in group:
                img=f'<img src="/media/{quote(photo["ref"])}" alt="Ponto {e(p["number"])}">' if photo['ref'] else '<p>Foto não informada</p>'
                notes=f'<h2>PONTO {e(short(p["number"],18))}</h2><p class="stage">{e(photo.get("stage","Detalhe"))}'+(f' · {part_number}/{total_parts}' if total_parts>1 else '')+'</p>'
                if p.get('coordinate'):notes+='<p class="photo-coordinate">UTM: '+e(coordinate_for_book(p))+'</p>'
                notes+=''.join('<h3>'+e(label)+'</h3><p>'+e(value)+'</p>' for label,value in part)
                body+=f'<div class="photo-row"><div class="photo-box">{img}</div><div class="photo-notes">{notes}</div></div>'
            if len(group)==1:body+='<div class="photo-row blank"><div class="photo-box">Espaço sem foto</div><div class="photo-notes"></div></div>'
            add(body+'</div>',klass='photos')
    conductors=book.get('conductors',[])
    conductor_cells=lambda c:[names[c['from_point']]+' → '+names[c['to_point']],c['movement'],c['code']+' '+c['description']+'\n'+c['gauge'],c['length'],c['count'],c['extra'],c['total']]
    for i,rows in enumerate(table_groups(conductors,conductor_cells,[10,12,29,10,4,10,10],175) or [[]]):
        body='<h2>Somagem dos condutores'+(' · continuação' if i else '')+'</h2><p>Total (m) = comprimento do trecho × número de condutores + acréscimo total.</p>'
        if not rows:body+='<p>'+('Sem movimentação de condutores nesta obra.' if book.get('no_conductors') else 'Condutores não informados.')+'</p>'
        else:
            body+='<table><colgroup>'+''.join(f'<col style="width:{width}%">' for width in [12,14,31,12,7,12,12])+'</colgroup><thead><tr><th>Trecho</th><th>Mov.</th><th>Condutor / bitola</th><th>Comp. m</th><th>Nº</th><th>Adic. m</th><th>Total m</th></tr></thead><tbody>'
            for c in rows:body+=f'<tr><td>{e(names[c["from_point"]])} → {e(names[c["to_point"]])}</td><td>{e(c["movement"])}</td><td>{e(c["code"])} {e(c["description"])}<br>{e(c["gauge"])}</td><td class="num">{n(c["length"])}</td><td class="num">{c["count"]}</td><td class="num">{n(c["extra"])}</td><td class="num">{n(c["total"])}</td></tr>'
            body+='</tbody></table>'
        add(body,'SOMAGEM DOS CONDUTORES')
    for rows in table_groups(book.get('conductor_totals',[]),lambda c:[c['movement'],c['code']+' '+c['description'],c['gauge'],c['total']],[15,42,17,13]):
        body='<h2>Totais por condutor e movimentação</h2><table><colgroup>'+''.join(f'<col style="width:{width}%">' for width in [18,46,20,16])+'</colgroup><thead><tr><th>Movimentação</th><th>Código / condutor</th><th>Bitola</th><th>Total m</th></tr></thead><tbody>'
        body+=''.join(f'<tr><td>{e(c["movement"])}</td><td>{e(c["code"])} {e(c["description"])}</td><td>{e(c["gauge"])}</td><td class="num">{n(c["total"])}</td></tr>' for c in rows)+'</tbody></table>'
        add(body,'SOMAGEM DOS CONDUTORES')
    details='\n'.join(label+': '+str(job.get(key,'')) for label,key in [('Obra / OS','work_order'),('Data','date'),('Responsável','responsible'),('Local','location'),('Observações','notes')] if job.get(key))
    if job.get('notes') or any(len(str(job.get(key,'')))>limit for key,limit in [('work_order',40),('date',20),('responsible',60),('location',100)]):
        for part in wrap_text(details,1800):add('<h2>Informações completas da obra</h2><p class="pre">'+e(part)+'</p>','OBSERVAÇÕES DA OBRA')
    pending=list(job['result'].get('pending',[]))+list(book.get('pending',[]))
    return document_html(job,pages,'Book da obra',pending,preview=preview)


def document_html(job,pages,title,pending,preview=False):
    html='<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+e(title)+' '+e(job['work_order'])+'</title><link rel="stylesheet" href="/book-print.css"></head><body>'
    html+='<nav class="print-toolbar"><strong>'+e(title)+' '+e(job['work_order'])+'</strong><button id="printBook">Imprimir / salvar PDF</button><span>'+str(len(pages))+' páginas</span></nav>'
    if pending:html+='<div class="print-alert">RASCUNHO — '+e(' '.join(pending))+'</div>'
    for index,(body,klass) in enumerate(pages):
        html+=f'<article class="book-page {klass}">{body}<footer><img src="/assets/rodape.png" alt="Energisa Mato Grosso do Sul"><span>'+('RASCUNHO · ' if pending else '')+f'Obra {e(short(job["work_order"],40))} · {index+1}/{len(pages)}</span></footer></article>'
    return (html+('' if preview else '<script src="/book-print.js"></script>')+'</body></html>').encode('utf-8')


def labor_totals(services):
    """Soma a mesma mão de obra entre pontos e variantes sem misturar operações."""
    totals={}
    for service in services:
        price,source=service_price(service,LABOR)
        key=(service.get('code') or service.get('labor_id'),service['operation'],service['scope'],service['description'],price)
        if key not in totals:
            totals[key]={k:service[k] for k in ('code','operation','scope','description')}
            totals[key]['quantity']=Decimal(0)
            totals[key].update(unit_price=price,price_source=source)
        totals[key]['quantity']+=Decimal(str(service['quantity']))
    for row in totals.values():row['total_price']=line_total(row['quantity'],row['unit_price'])
    order={'INSTALAR':0,'RETIRAR':1,'EXECUTAR':2}
    return sorted(totals.values(),key=lambda s:(order.get(s['operation'],3),s['code'],s['scope'],s['description']))


def materials_report_html(job):
    """PDF separado com somente os totais de mão de obra e de materiais."""
    result=job['result'];pages=[]
    def add(title,body):
        header=f'<header class="book-heading"><img src="/assets/engelmig.png" alt="Engelmig"><div><h1>MÃO DE OBRA E MATERIAIS</h1><strong>OBRA – {e(short(job["work_order"],40))}</strong></div><img src="/assets/energisa.png" alt="Energisa"></header><div class="book-meta">Data: {e(job.get("date"))} · Responsável: {e(short(job.get("responsible"),60))}<br>Local: {e(short(job.get("location"),100))}</div>'
        pages.append((header+'<h2>'+e(title)+'</h2>'+body,''))
    def table(headers,rows,widths,numeric=()):
        return '<table><colgroup>'+''.join(f'<col style="width:{w}%">' for w in widths)+'</colgroup><thead><tr>'+''.join('<th>'+e(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join(('<td class="num">' if i in numeric else '<td>')+e(c).replace('\n','<br>')+'</td>' for i,c in enumerate(row))+'</tr>' for row in rows)+'</tbody></table>'
    def labor_cells(s):
        price_label='Erro na origem' if s['price_source'].get('status')=='erro_na_origem' else 'Não informado'
        return [s['code'],s['description'],s['operation']+'\n'+s['scope'],n(s['quantity']),money(s['unit_price'],unit=True) if s['unit_price'] is not None else price_label,money(s['total_price']) if s['total_price'] is not None else '—']
    labor=labor_totals(result['services'])
    missing=sum(s['unit_price'] is None for s in labor)
    total=sum((s['total_price'] for s in labor if s['total_price'] is not None),Decimal(0))
    groups=table_groups(labor,labor_cells,[9,26,13,11,14,15],155) or [[]]
    for index,group in enumerate(groups):
        body=table(['Código','Mão de obra','Operação / escopo','Qtd.','Unitário (R$)','Total (R$)'],[labor_cells(s) for s in group],[10,31,17,11,15,16],numeric=(3,4,5)) if group else '<p>Sem lançamento.</p>'
        if labor and index==len(groups)-1:
            label='Subtotal com valor informado' if missing else 'Total da mão de obra'
            amount='Sem valores informados' if missing==len(labor) else 'R$ '+money(total)
            body+='<div class="labor-total"><strong>'+label+'</strong><strong>'+amount+'</strong></div>'
            if missing:body+='<p class="price-note">'+str(missing)+' linha(s) sem valor válido na planilha. O subtotal inclui somente as linhas com valor informado.</p>'
        if group:
            body+='<p class="price-note">Fonte: Mão de obra.xlsx · coluna VALOR. Unitários exibidos com até 6 casas decimais. O cálculo usa a precisão da planilha; cada total de linha é arredondado a centavos, e o total geral soma essas linhas.</p>'
            if any(s['price_source'].get('legacy_lookup') for s in group):body+='<p class="price-note">Registro anterior ao cadastro de valores: preços consultados na base atual.</p>'
        add('Total de mãos de obra'+(' · continuação' if index else ''),body)
    for movement,label in [('instalado','Materiais instalados'),('desativado','Materiais desativados')]:
        rows=[m for m in result['materials'] if m['movement']==movement]
        cells=lambda m:[m['code'],m['description'],m['unit'],n(m['quantity'])]
        for group in table_groups(rows,cells,[14,50,7,12],175) or [[]]:
            add(label,table(['Código','Descrição','Un.','Qtd.'],[cells(m) for m in group],[16,60,9,15]) if group else '<p>Sem lançamento.</p>')
    return document_html(job,pages,'Mão de obra e materiais',result.get('pending',[]))
