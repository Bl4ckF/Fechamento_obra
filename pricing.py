"""Preços da planilha: precisão decimal, memória do registro e apresentação BRL."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext


def clean_price(value):
    """None significa valor ausente; zero é um valor informado válido."""
    if value is None:return None
    raw=str(value)
    if len(raw)>120:raise ValueError('Valor de mão de obra inválido no registro.')
    try:amount=Decimal(raw)
    except (InvalidOperation,ValueError):raise ValueError('Valor de mão de obra inválido no registro.')
    if not amount.is_finite() or amount<0 or amount>Decimal('1e18') or amount.as_tuple().exponent < -30:
        raise ValueError('Valor de mão de obra inválido no registro.')
    text=format(amount,'f')
    return text.rstrip('0').rstrip('.') if '.' in text else text


def price_source(value):
    if not isinstance(value,dict):return {}
    return {key:str(value[key])[:240] for key in ('file','sheet','cell','raw','status','sha256') if key in value}


def service_price(service,catalog):
    # Obras gravadas com valor (inclusive None) conservam a cotação da época.
    if 'unit_price' in service:
        return clean_price(service['unit_price']),price_source(service.get('price_source'))
    # Registros anteriores à v11 ainda não continham valores. Só usar a base
    # atual se o identificador e a identidade do serviço corresponderem.
    source=catalog.get(service.get('labor_id'))
    if source and all(source.get(k)==service.get(k) for k in ('code','operation','scope','description')):
        return clean_price(source.get('unit_price')),dict(price_source(source.get('price_source')),legacy_lookup='true')
    return None,{}


def line_total(quantity,unit_price):
    if unit_price is None:return None
    with localcontext() as ctx:
        ctx.prec=60
        return (Decimal(str(quantity))*Decimal(unit_price)).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)


def money(value,unit=False):
    if value is None:return 'Não informado'
    with localcontext() as ctx:
        ctx.prec=60
        rounded=Decimal(str(value)).quantize(Decimal('.000001') if unit else Decimal('.01'),rounding=ROUND_HALF_UP)
        text=format(rounded,',.6f' if unit else ',.2f')
    if unit:
        integer,fraction=text.split('.')
        text=integer+'.'+fraction.rstrip('0').ljust(2,'0')
    return text.replace(',','_').replace('.',',').replace('_','.')
