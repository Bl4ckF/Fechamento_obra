"""Address suggestions and offline Google Earth import (standard library only)."""
import base64
import hashlib
import io
import json
import math
import threading
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET
import zipfile
from geo import valid_coord, format_utm, parse_coord

MAX_BYTES=10*1024*1024
MAX_VERTICES=20000
MAX_FEATURES=500
_cache={}
_lock=threading.Lock()
_last=0.0


def suggest(query):
    global _last
    query=str(query).strip()
    if not 4<=len(query)<=200:
        return {'results':[], 'source':'Photon / OpenStreetMap'}
    try:
        lat,lon=parse_coord(query)
        return {'results':[{'label':'Coordenada informada','lat':lat,'lon':lon,'utm':format_utm(lat,lon)}], 'source':'Coordenada local'}
    except ValueError:
        pass
    key=query.casefold()
    with _lock:
        now=time.monotonic()
        if key in _cache and now-_cache[key][0]<3600:return _cache[key][1]
        if now-_last<1:raise ValueError('Aguarde um instante antes de pesquisar novamente.')
        _last=now
        url='https://photon.komoot.io/api/?'+urlencode({'q':query,'limit':5})
        try:
            with urlopen(Request(url,headers={'User-Agent':'EngelmigFechamento/1.4.0 (address suggestions; https://github.com/Bl4ckF/fechamento_obra)'}),timeout=8) as response:
                raw=response.read(512001)
            if len(raw)>512000:raise ValueError('Resposta de endereços muito grande.')
            data=json.loads(raw)
        except (OSError,ValueError):
            raise ValueError('Busca online indisponível. Tente novamente ou informe coordenadas; KML/KMZ funciona offline.') from None
        rows=[]
        for f in data.get('features',[])[:5]:
            try:
                lon,lat=f['geometry']['coordinates'][:2];lat,lon=valid_coord(lat,lon)
                props=f.get('properties',{});parts=[]
                for field in ('name','street','housenumber','district','city','state','country'):
                    value=str(props.get(field) or '')[:150]
                    if value and value not in parts:parts.append(value)
                rows.append({'label':', '.join(parts) or 'Local aproximado','lat':lat,'lon':lon,'utm':format_utm(lat,lon)})
            except (ValueError,TypeError,KeyError):continue
        result={'results':rows,'source':'Photon / OpenStreetMap'}
        if len(_cache)>=100:_cache.pop(next(iter(_cache)))
        _cache[key]=(time.monotonic(),result)
        return result


def clean_features(features):
    if not isinstance(features,list) or len(features)>MAX_FEATURES:raise ValueError('Limite de 500 elementos geográficos por obra.')
    result=[];vertices=0;ids=set()
    def pair(p):
        nonlocal vertices
        if not isinstance(p,list) or len(p)!=2:raise ValueError('Coordenada geográfica inválida.')
        lat,lon=valid_coord(p[1],p[0]);format_utm(lat,lon)
        vertices+=1
        if vertices>MAX_VERTICES:raise ValueError('Limite de 20.000 vértices por obra.')
        return [lon,lat]
    for f in features:
        if not isinstance(f,dict):raise ValueError('Elemento geográfico inválido.')
        kind=f.get('type');coords=f.get('coordinates')
        if kind=='Point':coords=pair(coords)
        elif kind=='LineString':
            if not isinstance(coords,list) or not 2<=len(coords)<=MAX_VERTICES:raise ValueError('Linha precisa de pelo menos dois vértices.')
            coords=[pair(p) for p in coords]
        elif kind=='Polygon':
            if not isinstance(coords,list) or not 1<=len(coords)<=100:raise ValueError('Área inválida.')
            rings=[]
            for ring in coords:
                if not isinstance(ring,list) or not 4<=len(ring)<=MAX_VERTICES:raise ValueError('Contorno precisa de ao menos quatro vértices, incluindo fechamento.')
                ring=[pair(p) for p in ring]
                if ring[0]!=ring[-1]:raise ValueError('Contorno de área não está fechado.')
                rings.append(ring)
            coords=rings
        else:raise ValueError('Geometria não suportada.')
        name=str(f.get('name') or kind)[:200]
        ident=hashlib.sha256(json.dumps([kind,name,coords],ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
        if ident in ids:continue
        ids.add(ident)
        result.append({'id':ident,'name':name,'type':kind,'coordinates':coords,'source':str(f.get('source') or '')[:200]})
    return result


def import_earth(name,encoded):
    name=str(name)[:200]
    if not name.lower().endswith(('.kml','.kmz')):raise ValueError('Selecione um arquivo KML ou KMZ.')
    if not isinstance(encoded,str) or len(encoded)>MAX_BYTES*4//3+4:raise ValueError('Arquivo excede 10 MB.')
    try:raw=base64.b64decode(encoded,validate=True)
    except ValueError:raise ValueError('Arquivo inválido.') from None
    if len(raw)>MAX_BYTES:raise ValueError('Arquivo excede 10 MB.')
    documents=[]
    if name.lower().endswith('.kmz'):
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                entries=z.infolist()
                if len(entries)>200 or sum(f.file_size for f in entries)>20*1024*1024:raise ValueError('KMZ excede o limite descompactado de 20 MB / 200 arquivos.')
                kmls=[f for f in entries if f.filename.lower().endswith('.kml') and not f.is_dir()]
                if not 1<=len(kmls)<=10:raise ValueError('KMZ deve conter de 1 a 10 arquivos KML.')
                for f in kmls:
                    if f.file_size>MAX_BYTES:raise ValueError('KML interno excede 10 MB.')
                    documents.append(z.read(f))
        except (zipfile.BadZipFile,RuntimeError,NotImplementedError):raise ValueError('KMZ inválido ou protegido por senha.') from None
    else:documents=[raw]
    features=[];ignored=0;count=0
    def coordinates(element):
        nonlocal count
        if element is None:raise ValueError('Geometria sem coordenadas.')
        result=[]
        for token in (element.text or '').split():
            fields=token.split(',')
            if len(fields) not in (2,3):raise ValueError('Coordenada KML inválida.')
            try:lon,lat=float(fields[0]),float(fields[1])
            except ValueError:raise ValueError('Coordenada KML inválida.') from None
            valid_coord(lat,lon);format_utm(lat,lon)
            count+=1
            if count>MAX_VERTICES:raise ValueError('Limite de 20.000 vértices por arquivo.')
            result.append([lon,lat])
        return result
    for raw in documents:
        if b'<!DOCTYPE' in raw.upper().replace(b'\0',b'') or b'<!ENTITY' in raw.upper().replace(b'\0',b''):
            raise ValueError('KML com entidades ou DTD não é permitido.')
        try:tree=ET.fromstring(raw)
        except ET.ParseError:raise ValueError('XML do KML inválido.') from None
        for node in tree.iter():node.tag=node.tag.split('}')[-1]
        if tree.tag!='kml':raise ValueError('O arquivo não é um documento KML.')
        ignored+=sum(1 for node in tree.iter() if node.tag in ('NetworkLink','GroundOverlay','PhotoOverlay','Track'))
        for mark in tree.iter('Placemark'):
            label=mark.findtext('name') or 'Elemento Google Earth'
            for node in mark.iter():
                if node.tag not in ('Point','LineString','Polygon'):continue
                if node.tag=='Polygon':
                    outer=node.find('outerBoundaryIs/LinearRing/coordinates')
                    coords=[coordinates(outer)]+[coordinates(c) for c in node.findall('innerBoundaryIs/LinearRing/coordinates')]
                else:
                    coords=coordinates(node.find('coordinates'))
                    if node.tag=='Point':
                        if len(coords)!=1:raise ValueError('Marcador KML deve conter uma coordenada.')
                        coords=coords[0]
                features.append({'name':label,'type':node.tag,'coordinates':coords,'source':name})
                if len(features)>MAX_FEATURES:raise ValueError('Limite de 500 elementos por arquivo.')
    clean=clean_features(features)
    if not clean:raise ValueError('Nenhum ponto, linha ou área compatível encontrado. Exporte os elementos como KML/KMZ no Google Earth.')
    return {'features':clean,'warnings':(['Links externos, sobreposições ou trilhas animadas não foram importados.'] if ignored else []),'datum':'WGS84','vertices':count}
