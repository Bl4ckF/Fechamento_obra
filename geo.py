"""Consulta da base QField reutilizada do Book Poda 12.5, sem dependências."""
import json
import math
import re
from functools import lru_cache
from pathlib import Path

def valid_coord(lat, lon):
    lat, lon = float(lat), float(lon)
    if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError('Latitude ou longitude fora do intervalo válido.')
    return lat, lon

def utm_to_latlon(zone, band, east, north):
    if not (1 <= zone <= 60 and 100000 <= east <= 900000 and 0 <= north <= 10000000):
        raise ValueError('UTM fora do intervalo válido.')
    # WGS84 / SIRGAS2000 para consulta. Letra = faixa UTM (21K em Campo Grande).
    a, ecc, k = 6378137.0, 0.00669437999014, 0.9996
    x, y = east - 500000, north - (10000000 if band < 'N' else 0)
    mu = (y/k)/(a*(1-ecc/4-3*ecc**2/64-5*ecc**3/256))
    e1 = (1-math.sqrt(1-ecc))/(1+math.sqrt(1-ecc))
    fp = (mu+(3*e1/2-27*e1**3/32)*math.sin(2*mu)+(21*e1**2/16-55*e1**4/32)*math.sin(4*mu)
          +151*e1**3/96*math.sin(6*mu)+1097*e1**4/512*math.sin(8*mu))
    ep=ecc/(1-ecc); c=ep*math.cos(fp)**2; t=math.tan(fp)**2
    n=a/math.sqrt(1-ecc*math.sin(fp)**2); r=a*(1-ecc)/(1-ecc*math.sin(fp)**2)**1.5; d=x/(n*k)
    lat=fp-n*math.tan(fp)/r*(d*d/2-(5+3*t+10*c-4*c*c-9*ep)*d**4/24+(61+90*t+298*c+45*t*t-252*ep-3*c*c)*d**6/720)
    lon=(d-(1+2*t+c)*d**3/6+(5-2*c+28*t-3*c*c+8*ep+24*t*t)*d**5/120)/math.cos(fp)
    return valid_coord(math.degrees(lat), (zone-1)*6-180+3+math.degrees(lon))

def latlon_to_utm(lat,lon):
    """WGS84, série Transversa de Mercator; retorna fuso, faixa, E e N."""
    lat,lon=valid_coord(lat,lon)
    if not -80<=lat<=84:raise ValueError('UTM atende latitudes entre 80° S e 84° N.')
    zone=min(60,int((lon+180)//6)+1)
    if 56<=lat<64 and 3<=lon<12:zone=32
    if 72<=lat<=84 and 0<=lon<42:
        zone=31 if lon<9 else 33 if lon<21 else 35 if lon<33 else 37
    band='CDEFGHJKLMNPQRSTUVWXX'[min(20,int((lat+80)//8))]
    phi=math.radians(lat);lam=math.radians(lon);origin=math.radians(zone*6-183)
    a,e,k=6378137.0,0.00669437999014,0.9996
    ep=e/(1-e);n=a/math.sqrt(1-e*math.sin(phi)**2)
    t=math.tan(phi)**2;c=ep*math.cos(phi)**2;v=math.cos(phi)*(lam-origin)
    m=a*((1-e/4-3*e**2/64-5*e**3/256)*phi
         -(3*e/8+3*e**2/32+45*e**3/1024)*math.sin(2*phi)
         +(15*e**2/256+45*e**3/1024)*math.sin(4*phi)
         -35*e**3/3072*math.sin(6*phi))
    east=500000+k*n*(v+(1-t+c)*v**3/6+(5-18*t+t*t+72*c-58*ep)*v**5/120)
    north=k*(m+n*math.tan(phi)*(v*v/2+(5-t+9*c+4*c*c)*v**4/24
          +(61-58*t+t*t+600*c-330*ep)*v**6/720))
    if lat<0:north+=10000000
    return zone,band,east,north

def format_utm(lat,lon):
    zone,band,east,north=latlon_to_utm(lat,lon)
    return f'{zone}{band} {east:.0f} {north:.0f}'

def coordinate_for_book(point):
    value=point.get('coordinate')
    if not value:return ''
    try:return format_utm(*parse_coord(value))
    except (ValueError,TypeError):return 'Coordenada fora da faixa UTM ou inválida'

def parse_coord(value):
    """Read WGS84 coordinates; ambiguous projected values are never guessed."""
    s=str(value).strip().upper().replace('−','-').replace('–','-').replace('˚','°').replace('º','°')
    s=s.replace('′',"'").replace('’',"'").replace('″','"').replace('”','"')
    if len(s)>500:raise ValueError('Coordenada muito longa.')
    number=r'(\d{1,8}(?:[.,]\d+)?)'
    # Explicit hemisphere is different from a latitude band (21S is band S).
    hemisphere=re.fullmatch(r'(?:UTM\s*)?(?:FUSO\s*|ZONA\s*)?(\d{1,2})\s*(?:HEMISF[ÉE]RIO\s*)?(SUL|SOUTH|NORTE|NORTH)\s*[,;/ ]+\s*'+number+r'\s*[,;/ ]+\s*'+number,s)
    if hemisphere:
        return utm_to_latlon(int(hemisphere[1]),'K' if hemisphere[2] in ('SUL','SOUTH') else 'N',float(hemisphere[3].replace(',','.')),float(hemisphere[4].replace(',','.')))
    utm=re.fullmatch(r'(?:UTM\s*)?(?:ZONA\s*|FUSO\s*)?(\d{1,2})\s*([C-HJ-NP-X])\s*[,;/ ]+\s*'+number+r'\s*[,;/ ]+\s*'+number,s)
    if utm:
        return utm_to_latlon(int(utm[1]),utm[2],float(utm[3].replace(',','.')),float(utm[4].replace(',','.')))
    # Decimal, degrees/minutes and DMS with prefix or suffix cardinal directions.
    angle=r'([+-]?\d{1,3}(?:[.,]\d+)?)(?:\s*°\s*(?:(\d{1,2}(?:[.,]\d+)?)\s*\'\s*(?:(\d{1,2}(?:[.,]\d+)?)\s*"?)?)?)?'
    for pattern, prefix in [(r'([NSEWO])\s*'+angle,True),(angle+r'\s*([NSEWO])',False)]:
        matches=list(re.finditer(pattern,s))
        if len(matches)!=2:continue
        remainder=s
        for match in reversed(matches):remainder=remainder[:match.start()]+remainder[match.end():]
        if remainder.strip(' ,;/\t\r\n'):continue
        result={}
        for match in matches:
            g=match.groups()
            hem,deg,mins,secs=g if prefix else (g[3],g[0],g[1],g[2])
            d=float(deg.replace(',','.'));m=float((mins or '0').replace(',','.'));sec=float((secs or '0').replace(',','.'))
            if m>=60 or sec>=60 or (mins and not d.is_integer()) or (secs and not m.is_integer()):
                raise ValueError('Graus/minutos/segundos inválidos. Minutos e segundos devem ser menores que 60.')
            if d<0 and hem in 'NE':raise ValueError('Sinal negativo contradiz o hemisfério informado.')
            axis='lat' if hem in 'NS' else 'lon'
            if axis in result:raise ValueError('Informe uma latitude (N/S) e uma longitude (E/W/O).')
            result[axis]=(abs(d)+m/60+sec/3600)*(-1 if hem in 'SWO' else 1)
        return valid_coord(result['lat'],result['lon'])
    # Signed DMS/DDM without cardinals: latitude first, longitude second.
    signed=r'([+-]?\d{1,3})\s*°\s*(\d{1,2}(?:[.,]\d+)?)\s*\'\s*(?:(\d{1,2}(?:[.,]\d+)?)\s*")?'
    match=re.fullmatch(signed+r'\s*[,;/ ]+\s*'+signed,s)
    if match:
        out=[]
        for offset in (0,3):
            deg,minute,second=match.groups()[offset:offset+3]
            m=float(minute.replace(',','.'));sec=float((second or '0').replace(',','.'))
            if m>=60 or sec>=60 or (second and not m.is_integer()):raise ValueError('Minutos e segundos inválidos.')
            out.append((abs(float(deg))+m/60+sec/3600)*(-1 if deg.startswith('-') else 1))
        return valid_coord(*out)
    if re.search(r'\b(?:LATITUDE|LAT|LONGITUDE|LON|LONG)\b',s):
        labelled=re.fullmatch(r'(?:LATITUDE|LAT)\s*[:=]?\s*([+-]?\d{1,3}(?:[.,]\d+)?)\s*[,; ]+\s*(?:LONGITUDE|LONG|LON)\s*[:=]?\s*([+-]?\d{1,3}(?:[.,]\d+)?)',s)
        if not labelled:raise ValueError('Informe LAT primeiro e LON depois, ou use hemisférios N/S/E/W.')
        return valid_coord(float(labelled[1].replace(',','.')),float(labelled[2].replace(',','.')))

    parts=re.split(r'\s+|\s*;\s*',s)
    if len(parts)==2:
        try:return valid_coord(float(parts[0].rstrip(',').replace(',','.')),float(parts[1].replace(',','.')))
        except ValueError:pass
    decimal=re.fullmatch(r'([+-]?\d{1,3}(?:\.\d+)?)\s*,\s*([+-]?\d{1,3}(?:\.\d+)?)',s)
    if decimal:return valid_coord(decimal[1],decimal[2])
    raise ValueError('Formato não reconhecido. Use UTM com fuso/faixa (21K 753302 7725693), UTM com hemisfério (21 SUL 753302 7725693), decimal (-20.47, -54.62), DMS ou graus/minutos com S/W. Projeções ou datums diferentes precisam de conversão para WGS84.')


def coordinate_formats(lat,lon):
    lat,lon=valid_coord(lat,lon)
    def dms(value,positive,negative):
        seconds=round(abs(value)*3600,3)
        degrees=int(seconds//3600);seconds-=degrees*3600
        minutes=int(seconds//60);seconds-=minutes*60
        return f'{degrees}°{minutes:02d}\'{seconds:06.3f}"{negative if value<0 else positive}'
    return {'decimal':f'{lat:.8f}, {lon:.8f}',
            'dms':dms(lat,'N','S')+' '+dms(lon,'E','W'),
            'utm':format_utm(lat,lon) if -80<=lat<=84 else ''}

def distance(a,b,c,d):
    p,q=math.radians(a),math.radians(c)
    h=math.sin((q-p)/2)**2+math.cos(p)*math.cos(q)*math.sin(math.radians(d-b)/2)**2
    return 12742000*math.asin(min(1,math.sqrt(h)))

@lru_cache(maxsize=1)
def equipment():
    return json.loads((Path(__file__).parent/'data/qfield_equipment_index.json').read_text(encoding='utf-8'))

def nearest(lat,lon,radius=1200):
    radius=max(50,min(20000,float(radius)))
    found={'td':[],'rd':[]}
    for kind,code,y,x,circuit in equipment():
        if abs(y-lat)>radius/110000 or abs(x-lon)>radius/(110000*max(.05,abs(math.cos(math.radians(lat))))):continue
        dist=distance(lat,lon,y,x)
        if dist<=radius:found['td' if kind=='TD' else 'rd'].append({'kind':kind,'code':code,'lat':y,'lon':x,'circuit':circuit,'distance_m':round(dist,1)})
    for key in found:found[key]=sorted(found[key],key=lambda r:r['distance_m'])[:5]
    return found

def search(text,radius=1200):
    text=str(text).strip()
    try:
        lat,lon=parse_coord(text)
        return {'type':'coord','lat':lat,'lon':lon,'utm':format_utm(lat,lon) if -80<=lat<=84 else '', 'nearest':nearest(lat,lon,radius),'radius_m':radius}
    except ValueError:pass
    key=re.sub(r'[^A-Z0-9]','',text.upper())
    if len(key)<3:raise ValueError('Informe coordenadas ou ao menos três caracteres do TD, religador ou circuito.')
    hits=[]
    for kind,code,lat,lon,circuit in equipment():
        normalized=re.sub(r'[^A-Z0-9]','',code.upper())
        if key in normalized or key==str(circuit).upper():
            hits.append({'kind':kind,'code':code,'lat':lat,'lon':lon,'utm':format_utm(lat,lon),'circuit':circuit})
            if len(hits)==60:break
    if not hits:raise ValueError('Nenhum equipamento localizado nesta base. Confira o código ou o formato da coordenada.')
    return {'type':'equipment','results':hits}
