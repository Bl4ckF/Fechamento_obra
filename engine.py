"""Catálogos, sugestões explicáveis e cálculo decimal do fechamento."""
import json
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from pathlib import Path
from pricing import clean_price, price_source

ROOT = Path(__file__).resolve().parent
CATALOG = json.loads((ROOT/'data/catalogos.json').read_text(encoding='utf-8'))
BASE_DATA = json.loads((ROOT/'data/composicoes_material.json').read_text(encoding='utf-8'))
CATALOG['materials'].extend(BASE_DATA['extra_materials'])
BASES = {x['id']:x for x in BASE_DATA['variants']}
MATERIALS = {x['id']: x for x in CATALOG['materials']}
LABOR = {x['id']: x for x in CATALOG['labor']}

def norm(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(value)).upper() if not unicodedata.combining(c))

# These are search rules, never an official bill of materials. No quantity is inferred.
# Family, words in the supplied service description, catalog words.
RULES = [
    ('Cruzetas', r'\bCRUZET[AO]S?\b', r'^CRUZETA\b'),
    ('Pinos', r'\bPINOS?\b', r'^PINO\b'),
    ('Isoladores', r'\bISOLADOR(?:ES)?\b', r'^ISOLADOR\b'),
    ('Fixações', r'\bFIXAC(?:AO|OES)\b|\bFERRAGENS\b', r'^(?:PARAFUSO|PORCA|ARRUELA|CINTA|SUPORTE)\b'),
    ('Parafusos', r'\bPARAFUSOS?\b', r'^PARAFUSO\b'),
    ('Porcas', r'\bPORCAS?\b', r'^PORCA\b'),
    ('Arruelas', r'\bARRUELAS?\b', r'^ARRUELA\b'),
    ('Cintas', r'\bCINTAS?\b', r'^CINTA\b'),
    ('Suportes', r'\bSUPORTES?\b', r'^SUPORTE\b'),
    ('Mãos francesas', r'\bMAO FRANCESA\b|\bMAOS FRANCESAS\b', r'^MAO FRANCESA\b'),
    ('Transformadores', r'\bTRANSFORMADOR(?:ES)?\b|^TRANSF\b', r'^(?:TRANSF(?:ORMADOR)?|TRAFO)\b'),
    ('Religadores', r'\bRELIGADOR(?:ES)?\b', r'^RELIGADOR\b'),
    ('Reguladores', r'\bREGULADOR(?:ES)?\b', r'^REGULADOR\b'),
    ('Capacitores', r'\bCAPACITOR(?:ES)?\b', r'^(?:CAPACITOR|BANCO CAPAC)\b'),
    ('Chaves fusíveis', r'\bCHAVES? FUSIVE(?:L|IS)\b', r'^CHAVE FUS'),
    ('Chaves seccionadoras', r'\bCHAVES? (?:SECCIONADORAS?|FACA)\b', r'^CHAVE (?:SECC|FACA)'),
    ('Chaves', r'\bCHAVES?\b', r'^CHAVE\b'),
    ('Elos fusíveis', r'\bELOS? FUSIVE(?:L|IS)\b', r'^ELO\b'),
    ('Cartuchos e porta-fusíveis', r'\bCARTUCHOS?\b|\bPORTA[ -]?FUS', r'^(?:CARTUCHO|PORTA[ -]?FUS)'),
    ('Para-raios', r'\bPARA[ -]?RAIOS?\b', r'^PARA[ -]?RAIO'),
    ('Conectores', r'\bCONECTOR(?:ES)?\b', r'^CONEC(?:TOR)?\b'),
    ('Terminais', r'\bTERMINA(?:L|IS)\b', r'^(?:TERMINAL|CONECTOR TERM)\b'),
    ('Muflas', r'\bMUFLAS?\b', r'^(?:MUFLA|TERMINAL CONTR|TERMINAL EXT|TERMINAL INT)'),
    ('Hastes de aterramento', r'\bHASTES?\b', r'^HASTE\b'),
    ('Concreto e cimento', r'\bCONCRETAR\b|\bCONCRETAGEM\b|\bCIMENTO\b', r'^(?:CIMENTO|CONCRETO)\b'),
    ('Cabos e condutores', r'\bCABOS?\b|\bCONDUTOR(?:ES)?\b', r'^(?:CABO|FIO)\b'),
    ('Alças', r'\bALCAS?\b', r'^ALCA\b'),
    ('Laços', r'\bLACOS?\b', r'^LACO\b'),
    ('Grampos', r'\bGRAMPOS?\b', r'^GRAMPO\b'),
    ('Emendas', r'\bEMENDAS?\b', r'^EMENDA\b|^LUVA (?:EMENDA|ALUM|COBRE|ACO|COMPRESS)'),
    ('Espaçadores', r'\bESPACADOR(?:ES)?\b', r'^ESPACADOR\b'),
    ('Separadores', r'\bSEPARADOR(?:ES)?\b', r'^SEPARADOR\b'),
    ('Estribos', r'\bESTRIBOS?\b', r'^(?:ESTRIBO|ALCA ESTRIBO)\b'),
    ('Sapatilhas', r'\bSAPATILHAS?\b', r'^SAPATILHA\b'),
    ('Olhais', r'\bOLHA(?:L|IS)\b', r'^(?:OLHAL|PARAFUSO OLHAL)\b'),
    ('Armações', r'\bARMACOES\b|\bARMACAO\b', r'^ARMACAO\b'),
    ('Eletrodutos', r'\bELETRODUTOS?\b', r'^(?:ELETRODUTO|DUTO)\b'),
    ('Caixas', r'\bCAIXAS?\b', r'^CAIXA\b'),
    ('Tampas', r'\b(?:SUB)?TAMPAS?\b', r'^(?:TAMPA|SUBTAMPA)\b'),
    ('Lacres', r'\bLACRES?\b', r'^LACRE\b'),
    ('Medidores', r'\bMEDIDOR(?:ES)?\b', r'^MEDIDOR\b'),
    ('Disjuntores', r'\bDISJUNTOR(?:ES)?\b', r'^DISJUNTOR\b'),
    ('Fitas', r'\bFITAS?\b', r'^FITA\b'),
    ('Abraçadeiras', r'\bABRACADEIRAS?\b', r'^ABRACADEIRA\b'),
    ('Arames', r'\bARAMES?\b', r'^ARAME\b'),
    ('Postes', r'\bPOSTES?\b', r'^POSTE\b'),
    ('Braços', r'\bBRACOS?\b', r'^BRACO\b'),
    ('Luminárias', r'\bLUMINARIAS?\b', r'^LUMINARIA\b'),
    ('Lâmpadas', r'\bLAMPADAS?\b', r'^LAMPADA\b'),
    ('Relés', r'\bRELES?\b', r'^RELE\b'),
    ('Antenas', r'\bANTENAS?\b', r'^ANTENA\b'),
    ('Cordoalhas', r'\bCORDOALHAS?\b', r'^CORDOALHA\b'),
    ('Afastadores', r'\bAFASTADOR(?:ES)?\b', r'^AFASTADOR\b'),
    ('Prolongadores', r'\bPROLONGADOR(?:ES)?\b', r'^PROLONGADOR\b'),
    ('Placas de identificação', r'\bPLACA DE IDENTIFICACAO\b|\bNUMEROS OPERATIVOS\b', r'^(?:PLACA|NUMERO|ALGARISMO)\b'),
    ('Seccionadores', r'\bSECCIONADOR(?:ES)?\b', r'^SECCIONADOR\b'),
    ('Mourões', r'\bMO[UI]R(?:AO|OES)\b', r'^MO[UI]R(?:AO|OES)\b'),
    ('Defensas', r'\bDEFENSAS?\b', r'^DEFENSA\b'),
    ('Sinalizadores de falta', r'\bSINALIZADOR(?:ES)?\b', r'^(?:SINALIZADOR|INDICADOR)\b'),
    ('Conjuntos de suspensão', r'CONJUNTO DE ELEVACAO|CONJUNTO DE SUSPENSAO', r'^CONJUNTO.*(?:SUSP|ELEV)'),
    ('Anéis', r'\bANE(?:L|IS)\b', r'^ANEL\b'),
    ('Buchas', r'\bBUCHAS?\b', r'^BUCHA\b'),
    ('Ganchos', r'\bGANCHOS?\b', r'^GANCHO\b'),
    ('Travas', r'\bTRAVAS?\b', r'^TRAVA\b'),
]
MATERIAL_NORM = {k:norm(v['description']) for k,v in MATERIALS.items()}
FAMILY_MATERIALS = {name:[k for k,v in MATERIAL_NORM.items() if re.search(mp,v)] for name,_,mp in RULES}

def suggestions(labor_id):
    service = LABOR[labor_id]
    title = norm(service['description'])
    lines = [service['description']] + [x.strip() for x in service['detail'].splitlines() if x.strip()]
    groups = []
    for name, pattern, _ in RULES:
        evidence = []
        for line in lines:
            n = norm(line)
            if not re.search(pattern,n): continue
            if re.search(r'NAO (?:CONSIDERA|CONTEMPLA)|SERAO REMUNERAD|COBERTURAS|PROVISORI|TEMPORARI', n): continue
            # A pole mentioned only as a support is not itself being installed/removed.
            if name == 'Postes' and not re.search(r'\bPOSTES?\b',title): continue
            # Conductors only tied/untied or connected are not necessarily replaced.
            if name == 'Cabos e condutores' and not re.search(r'\bCABOS?\b|\bCONDUTOR',title):
                if not re.search(r'(?:LANCAR|INSTALAR|RETIRAR|REMOVER|RECOLHER|CORTAR|SUBSTITUIR|APLICAR)\s+(?:(?:O|OS|UM|NOVO|NOVOS)\s+)?(?:CABOS?|CONDUTOR)',n): continue
            evidence.append(line)
        if not evidence: continue
        ids = FAMILY_MATERIALS[name]
        # Order, never silently discard alternatives. Similar words do not establish equivalence.
        words=set(re.findall(r'[A-Z0-9.,/]+',title)) - {'INSTALAR','RETIRAR','LM','LV','SDMT','SDBT','DE','DO','DA','ESTRUTURA'}
        def rank(mid):
            text = MATERIAL_NORM[mid]
            score=sum((4 if re.search(r'\d',w) else 1) for w in words if len(w)>1 and w in text)
            for source,abbr in [('CONCRETO','CONC'),('POLIMERICA','POLIM'),('MADEIRA','MAD')]:
                if source in title and abbr in text: score+=3
            return score
        ids = sorted(ids,key=lambda k:(-rank(k),MATERIALS[k]['description']))
        groups.append({'name':name,'evidence':evidence[:2],'material_ids':ids,'total':len(ids)})
    if any(g['name'] in ('Chaves fusíveis','Chaves seccionadoras') for g in groups):
        groups=[g for g in groups if g['name']!='Chaves']
    return {'labor_id':labor_id,'groups':groups,'source':f"{service['sheet']} · linha {service['row']}",
            'notice':'Sugestões por palavras da descrição. As alternativas não formam uma lista completa nem uma composição oficial. Confira modelo, unidade, quantidade e aplicação.'}

def positive(value, label):
    try: result = Decimal(str(value).strip().replace(',','.'))
    except (InvalidOperation,ValueError): raise ValueError(f'{label}: informe uma quantidade válida.')
    if not result.is_finite() or result <= 0 or result > Decimal('1000000000'):
        raise ValueError(f'{label}: use um número maior que zero e até 1 bilhão.')
    if max(0,-result.as_tuple().exponent) > 6:
        raise ValueError(f'{label}: use no máximo 6 casas decimais.')
    return result

def decimal_text(value):
    return format(value,'f').rstrip('0').rstrip('.') if '.' in format(value,'f') else str(value)

def clean_rows(rows):
    if not isinstance(rows,list) or len(rows)>2000: raise ValueError('Lista de materiais inválida.')
    result=[]
    for row in rows:
        mat=MATERIALS.get(row.get('material_id'))
        if not mat: raise ValueError('Material fora do catálogo.')
        unit=str(row.get('unit','')).strip().upper()
        if mat['unit']: unit=mat['unit']
        if not re.fullmatch(r'[A-Z0-9²³/ ._-]{1,16}',unit): raise ValueError(f"Informe a unidade de {mat['code'] or mat['description']}.")
        if not mat['code']: raise ValueError('Este material está sem código na planilha. Use um registro com código.')
        movement=row.get('movement')
        if movement not in ('instalado','desativado'): raise ValueError('Escolha instalado ou desativado para cada material.')
        q=positive(row.get('coefficient'),'Quantidade por serviço')
        result.append({'material_id':mat['id'],'code':mat['code'],'description':mat['description'], 'unit':unit,
                       'unit_source':'catalogo' if mat['unit'] else 'informada', 'movement':movement, 'coefficient':decimal_text(q)})
    return result

def structure_description(service):
    """Usa a estrutura efetivamente escolhida, inclusive em registros antigos."""
    base=BASES.get(service.get('base_id',''))
    if base and base['kind']=='structure':
        params=base['params'];label='Estrutura '+params['structure']
        if params.get('pole'):label+=' · poste '+params['pole']
        if service.get('context'):label+=' · '+service['context']
        return label
    return service.get('description','')

def clean_service(item):
    service=LABOR.get(item.get('labor_id'))
    if not service: raise ValueError('Mão de obra fora do catálogo.')
    quantity=positive(item.get('quantity'),'Quantidade de mão de obra')
    rows=clean_rows(item.get('materials',[]))
    no_materials=item.get('no_materials') is True
    if no_materials and rows: raise ValueError('Serviço sem material não pode conter materiais.')
    reviewed=item.get('reviewed') is True
    if reviewed and not rows and not no_materials: raise ValueError('Adicione materiais ou confirme serviço sem material.')
    base_id=str(item.get('base_id',''))
    if base_id and base_id not in BASES: raise ValueError('Composição-base não encontrada nesta versão.')
    mode=str(item.get('base_mode','manual'))
    if mode not in ('manual','planilha','instalado','desativado'): raise ValueError('Filtro de movimentação inválido.')
    return {'labor_id':service['id'],'code':service['code'],'description':service['description'],
            'scope':service['scope'],'operation':service['operation'],'us':service['us'],'source':f"{service['sheet']} · linha {service['row']}",
            'unit_price':clean_price(service.get('unit_price')),'price_source':price_source(service.get('price_source')),
            'quantity':decimal_text(quantity),'materials':rows,'reviewed':reviewed,'no_materials':no_materials,
            'point_id':str(item.get('point_id',''))[:80],
            'entry_id':str(item.get('entry_id',''))[:80],
            'variant':str(item.get('variant',''))[:240],'note':str(item.get('note',''))[:2000],
            'base_id':base_id,'base_mode':mode,'context':str(item.get('context','')).strip()[:160],
            'memory_revision':item.get('memory_revision') if isinstance(item.get('memory_revision'),int) else None,
            'source_hash':str(item.get('source_hash',''))[:64]}

def calculate(items):
    if not isinstance(items,list) or len(items)>1000: raise ValueError('Lista de serviços inválida.')
    normalized=[clean_service(s) for s in items]
    totals={}
    pending=[]
    us_total=Decimal(0)
    us_missing=0
    for index,s in enumerate(normalized):
        if not s['code']: pending.append(f"Serviço {index+1}: código de mão de obra ausente na origem.")
        if not s['reviewed']: pending.append(f"Serviço {index+1} ({s['code'] or 'sem código'}): composição não conferida.")
        q=Decimal(s['quantity'])
        if s['us'] is None: us_missing+=1
        else: us_total+=Decimal(str(s['us']))*q
        for m in s['materials']:
            key=(m['code'],m['unit'],m['movement'])
            if key not in totals:
                totals[key]={k:m[k] for k in ('code','description','unit','movement')}
                totals[key].update(quantity=Decimal(0),services=[])
            totals[key]['quantity']+=Decimal(m['coefficient'])*q
            totals[key]['services'].append(f"{s['code'] or 'sem código'} {s['operation']} × {s['quantity']} (item {index+1})")
    rows=sorted(totals.values(),key=lambda r:(r['movement'],r['description'],r['code'],r['unit']))
    # Unknown units manually provided for a code must agree across the whole work order.
    units={}
    for r in rows:
        units.setdefault(r['code'],set()).add(r['unit'])
        r['quantity']=decimal_text(r['quantity'])
    for code,values in units.items():
        if len(values)>1: pending.append(f"Material {code}: unidades divergentes ({', '.join(sorted(values))}).")
    return {'services':normalized,'materials':rows,'pending':pending,'ready':bool(normalized) and not pending,
            'us_total':decimal_text(us_total),'us_missing':us_missing}

def clean_profile(profile):
    clean=clean_service({**profile,'quantity':'1','reviewed':True})
    clean['point_id']='';clean['entry_id']=''
    if not clean['variant'].strip(): raise ValueError('Dê um nome para a composição, incluindo a variante.')
    return clean
