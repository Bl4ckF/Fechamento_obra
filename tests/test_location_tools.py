import base64
import io
import json
import unittest
import zipfile
from unittest.mock import patch
import book
import geo
import location_tools as loc

KML='''<kml xmlns="http://www.opengis.net/kml/2.2"><Document>
<Placemark><name>Ponto A</name><Point><coordinates>-54.62,-20.47,100</coordinates></Point></Placemark>
<Placemark><name>Trecho</name><LineString><coordinates>-54.62,-20.47 -54.621,-20.471</coordinates></LineString></Placemark>
<Placemark><name>Área</name><Polygon><outerBoundaryIs><LinearRing><coordinates>-54.62,-20.47 -54.63,-20.47 -54.63,-20.48 -54.62,-20.47</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>
<NetworkLink><Link><href>https://example.invalid/no-fetch</href></Link></NetworkLink>
</Document></kml>'''
def encoded(text):return base64.b64encode(text.encode()).decode()

class EarthTests(unittest.TestCase):
    def test_kml_points_lines_polygons_and_no_links(self):
        with patch('location_tools.urlopen') as request:
            result=loc.import_earth('projeto.kml',encoded(KML))
        request.assert_not_called()
        self.assertEqual([f['type'] for f in result['features']],['Point','LineString','Polygon'])
        self.assertEqual(result['vertices'],7)
        self.assertTrue(result['warnings'])
        self.assertTrue(geo.format_utm(-20.47,-54.62).startswith('21K '))

    def test_kmz_does_not_extract_files(self):
        buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,'w') as z:
            z.writestr('doc.kml',KML)
            z.writestr('../../arbitrary.txt','not extracted')
        result=loc.import_earth('projeto.kmz',base64.b64encode(buffer.getvalue()).decode())
        self.assertEqual(len(result['features']),3)

    def test_persists_in_normalized_book_and_deduplicates(self):
        features=loc.import_earth('projeto.kml',encoded(KML))['features']
        normalized=book.normalize_book({'geography':features+features},[])
        self.assertEqual(normalized['geography'],features)
        self.assertEqual(book.normalize_book(normalized,[])['geography'],features)
        self.assertEqual(book.normalize_book({},[])['geography'],[])

    def test_rejects_entities_and_bad_coordinates(self):
        for xml in ['<!DOCTYPE kml [<!ENTITY a "test">]><kml/>', KML.replace('-54.62,-20.47,100','NaN,-20.47'),KML.replace('-54.62,-20.47,100','-54,90'), '<notkml/>']:
            with self.subTest(xml=xml[:30]),self.assertRaises(ValueError):loc.import_earth('x.kml',encoded(xml))

    def test_limits_and_closed_polygon(self):
        with self.assertRaises(ValueError):loc.clean_features([{}]*501)
        with self.assertRaises(ValueError):loc.clean_features([{'type':'Polygon','coordinates':[[[0,0],[1,0],[1,1],[0,1]]]}])
        with self.assertRaises(ValueError):loc.import_earth('x.kml','A'*(loc.MAX_BYTES*4//3+5))
        with self.assertRaises(ValueError):loc.import_earth('x.pdf',encoded(KML))

    def test_coordinate_roundtrip_and_zones(self):
        for lat,lon in [(-20.47,-54.62),(-23.55,-46.63),(0,180),(60,6),(76,15)]:
            z,b,e,n=geo.latlon_to_utm(lat,lon)
            a,c=geo.utm_to_latlon(z,b,e,n)
            self.assertAlmostEqual(a,lat,places=5);self.assertAlmostEqual(c,lon,places=5)

class AddressTests(unittest.TestCase):
    def setUp(self):loc._cache.clear();loc._last=0
    def test_coordinate_search_is_offline(self):
        with patch('location_tools.urlopen') as request:
            result=loc.suggest('-20.47, -54.62')
        request.assert_not_called();self.assertEqual(result['results'][0]['utm'],geo.format_utm(-20.47,-54.62))
    def test_provider_cache_and_label(self):
        payload={'features':[{'geometry':{'coordinates':[-54.62,-20.47]},'properties':{'name':'Praça','city':'Campo Grande','country':'Brasil'}}]}
        with patch('location_tools.urlopen',return_value=io.BytesIO(json.dumps(payload).encode())) as request:
            result=loc.suggest('Campo Grande');self.assertEqual(loc.suggest('Campo Grande'),result)
        self.assertEqual(request.call_count,1);self.assertEqual(result['results'][0]['label'],'Praça, Campo Grande, Brasil')
    def test_offline_does_not_invent_results(self):
        with patch('location_tools.urlopen',side_effect=OSError('offline')),self.assertRaisesRegex(ValueError,'indisponível'):
            loc.suggest('Campo Grande')
