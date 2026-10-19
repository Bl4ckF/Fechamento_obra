"""Extrai somente Mão de obra.xlsx e MATERIAL.xlsm. Não executa VBA ou vínculos.

Os identificadores existentes são reutilizados por código/escopo/operação para
preservar registros. Descrições, unidades, preços e composições vêm das duas
fontes atuais; registros removidos não são reaproveitados como catálogo.
"""
import hashlib
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
RID='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
ROOT=Path(__file__).resolve().parents[1]


def read_workbook(path):
    result={}
    with zipfile.ZipFile(path) as z:
        strings=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            strings=[''.join(t.text or '' for t in item.iter('{'+NS['s']+'}t')) for item in ET.fromstring(z.read('xl/sharedStrings.xml'))]
        rels={item.get('Id'):item.get('Target') for item in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        for sheet in ET.fromstring(z.read('xl/workbook.xml')).find('s:sheets',NS):
            target=rels[sheet.get(RID)];target=target.lstrip('/') if target.startswith('/') else 'xl/'+target
            rows={}
            for row in ET.fromstring(z.read(target)).findall('s:sheetData/s:row',NS):
                cells={}
                for c in row.findall('s:c',NS):
                    value=c.find('s:v',NS);value=value.text if value is not None and value.text else ''
                    if c.get('t')=='s':value=strings[int(value)]
                    elif c.get('t')=='inlineStr':value=''.join(t.text or '' for t in c.iter('{'+NS['s']+'}t'))
                    if value:cells[re.sub(r'\d','',c.get('r'))]=value.strip()
                if cells:rows[int(row.get('r'))]=cells
            result[sheet.get('name')]=rows
    return result


def decimal_value(raw):
    try:value=Decimal(raw)
    except (InvalidOperation,ValueError):return None
    return value if value.is_finite() and value>=0 else None


def decimal_text(value):
    value=format(value,'f')
    return value.rstrip('0').rstrip('.') if '.' in value else value


def extract(root=ROOT):
    root=Path(root);sources=root/'fontes';material_file=sources/'MATERIAL.xlsm';labor_file=sources/'Mão de obra.xlsx'
    material_book=read_workbook(material_file);labor_book=read_workbook(labor_file)
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [labor_file,material_file]}
    existing=json.loads((root/'data/catalogos.json').read_text(encoding='utf-8')) if (root/'data/catalogos.json').exists() else {}
    previous_base=root/'data/composicoes_material.json'
    previous_base=json.loads(previous_base.read_text(encoding='utf-8')) if previous_base.exists() else {}
    old_materials=existing.get('materials',[])+previous_base.get('extra_materials',[])
    old_ids={m['code']:m['id'] for m in old_materials if m.get('code')}
    old_labor=defaultdict(list)
    for row in existing.get('labor',[]):old_labor[(row['sheet'],row['code'],row['scope'],row['operation'],row['description'])].append(row)
    materials=[];by_code={}
    for row,d in material_book['Lista de Materiais'].items():
        if row==1:continue
        code=d.get('B','');description=d.get('C','')
        if not code or not description:raise ValueError(f'Material incompleto na linha {row}.')
        if code in by_code:raise ValueError(f'Código de material repetido na origem: {code}.')
        item={'id':old_ids.get(code,'mat_'+code),'code':code,'description':description,'unit':d.get('D',''),
              'class':d.get('A',''),'row':row,'sheet':'Lista de Materiais','source_file':material_file.name}
        materials.append(item);by_code[code]=item
    labor=[];missing=[];used_ids=set()
    for index,(sheet,rows) in enumerate(labor_book.items(),1):
        header=next(d for d in rows.values() if 'OPERAÇÃO' in d.values())
        cols={value:key for key,value in header.items()}
        required=['Escopo','Cód_SIAGO','OPERAÇÃO','US']
        if any(k not in cols for k in required):raise ValueError('Cabeçalhos de mão de obra inválidos em '+sheet)
        description_col=cols.get('DESCRIÇÃO SIAGO',cols.get('DESCRIÇÃO BREVE'))
        for row,d in rows.items():
            if d.get(cols['OPERAÇÃO']) not in ('INSTALAR','RETIRAR','EXECUTAR'):continue
            code=d.get(cols['Cód_SIAGO'],'');scope=d.get(cols['Escopo'],'');operation=d[cols['OPERAÇÃO']];description=d.get(description_col,'')
            key=(sheet,code,scope,operation,description);candidates=old_labor.get(key,[])
            match=next((item for item in candidates if item['row']==row and item['id'] not in used_ids),None)
            if not match:match=next((item for item in candidates if item['id'] not in used_ids),None)
            ident=match['id'] if match else f's{index}r{row}'
            if ident in used_ids:raise ValueError('Identificador duplicado de mão de obra.')
            used_ids.add(ident);us=d.get(cols['US'],'');us_value=decimal_value(us)
            raw=d.get(cols.get('VALOR'),'');price=decimal_value(raw)
            # Conserva a precisão integral do valor calculado e salvo no arquivo.
            if price is not None:price=decimal_text(price)
            status='informado' if price is not None else 'erro_na_origem' if raw.startswith('#') else 'nao_informado'
            source={'file':labor_file.name,'sheet':sheet,'cell':cols['VALOR']+str(row) if 'VALOR' in cols else '', 'raw':raw,'status':status,'sha256':hashes[labor_file.name]}
            if price is None:missing.append({'labor_id':ident,**source})
            labor.append({'id':ident,'code':code,'scope':scope,'operation':operation,'description':description,
                          'detail':d.get(cols.get('DESCRIÇÃO DETALHADA'),''),'reference':d.get(cols.get('IT'),''),
                          'us':float(us_value) if us_value is not None else None,'us_source':us,'unit_price':price,'price_source':source,
                          'row':row,'sheet':sheet,'source_file':labor_file.name})
    variants=[];extra=[];source_counts={}
    for sheet,kind,cols,names in [('Dados - Estrutura','structure','AB',['pole','structure']),('Dados - Transformador','transformer','ABCDEF',['phase','voltage','power','fuse_position','bt_type','bt_exit'])]:
        groups={};count=0
        for row,d in material_book[sheet].items():
            if row<=1 or not d.get('A'):continue
            count+=1;params={name:d.get(col,'') for name,col in zip(names,cols)};key=tuple(params.values())
            if key not in groups:
                stable=hashlib.sha256(json.dumps([kind,*key],ensure_ascii=False).encode()).hexdigest()[:16]
                groups[key]={'id':kind+'_'+stable,'kind':kind,'params':params,'title':' · '.join(key),'sheet':sheet,'rows':[],'source_rows':[],'warnings':[]}
            variant=groups[key];variant['source_rows'].append(row);cc,dc=('C','D') if kind=='structure' else ('G','H');code=d.get(cc)
            if not code:raise ValueError(f'Código ausente em {sheet}, linha {row}.')
            if code not in by_code:
                item={'id':old_ids.get(code,'mat_'+code),'code':code,'description':d.get(dc,''),'unit':'','row':row,'sheet':sheet,'source_file':material_file.name}
                by_code[code]=item;extra.append(item)
            item=by_code[code]
            if not item['unit']:
                warning=f"Material {code}: unidade ausente na planilha; informe na primeira utilização."
                if warning not in variant['warnings']:variant['warnings'].append(warning)
            for col,movement in ([('E','context')] if kind=='structure' else [('I','instalado'),('J','desativado')]):
                raw=d.get(col,'')
                if not raw:continue
                q=decimal_value(raw)
                if q is None:raise ValueError(f'Quantidade inválida em {sheet}!{col}{row}.')
                if q==0:continue
                variant['rows'].append({'material_id':item['id'],'code':code,'unit':item['unit'],'coefficient':decimal_text(q),'movement':movement,
                  'source_description':d.get(dc,''),'source_cell':f'{sheet}!{col}{row}','code_cell':f'{sheet}!{cc}{row}'})
        source_counts[sheet]=count;variants.extend(groups.values())
    catalog={'schema':2,'source_materials':material_file.name,'source_labor':labor_file.name,'source_sha256':hashes,
             'currency':'BRL','materials':materials,'labor':labor,'price_issues':missing}
    bases={'schema':2,'source_file':material_file.name,'source_sha256':hashes[material_file.name],
           'variants':variants,'extra_materials':extra,'equipment_references':[],'source_counts':source_counts,
           'notes':['Catálogo e composições extraídos somente de MATERIAL.xlsm.','INST. e DESAT. preservados separadamente.','Não há tabela Cód. Trafo nesta fonte.','Macros e vínculos externos não são executados.']}
    return catalog,bases


def main():
    catalog,bases=extract();(ROOT/'data/catalogos.json').write_text(json.dumps(catalog,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    (ROOT/'data/composicoes_material.json').write_text(json.dumps(bases,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print(json.dumps({'labor':len(catalog['labor']),'materials':len(catalog['materials'])+len(bases['extra_materials']),'bases':len(bases['variants']),'without_price':len(catalog['price_issues'])}))

if __name__=='__main__':main()
