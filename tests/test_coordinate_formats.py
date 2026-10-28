import unittest
import geo

class CoordinateFormatsTests(unittest.TestCase):
 def test_common_formats(self):
  for text in ['-20.47, -54.62','-20,47; -54,62','20.47 S 54.62 W','S20.47 W54.62','20°28\'12"S 54°37\'12"W','S20°28\'12" W54°37\'12"','20°28.2\'S 54°37.2\'W','20°28,2\'S 54°37,2\'O','-20°28\'12"; -54°37\'12"','54°37.2\'W 20°28.2\'S','LAT: -20.47; LON: -54.62']:
   with self.subTest(text=text):
    lat,lon=geo.parse_coord(text);self.assertAlmostEqual(lat,-20.47);self.assertAlmostEqual(lon,-54.62)
 def test_explicit_southern_utm(self):
  a=geo.parse_coord('21K 753302 7725693')
  for value in ['UTM 21 SUL 753302 7725693','FUSO 21 HEMISFÉRIO SUL 753302 7725693']:
   self.assertEqual(geo.parse_coord(value),a)
 def test_invalid_is_not_guessed(self):
  for value in ['20°60\'S 54°37\'W','20°28\'70"S 54°37\'12"W','abc 20°28\'12"S 54°37\'12"W','20 S 54 S','-20 N 54 W','753302 7725693','21 753302 7725693']:
   with self.subTest(value=value),self.assertRaises(ValueError):geo.parse_coord(value)
 def test_formats_roundtrip(self):
  for pair in [(-20.47,-54.62),(51.5,-.12),(0,0),(89,100)]:
   formats=geo.coordinate_formats(*pair)
   for output in ('decimal','dms'):
    lat,lon=geo.parse_coord(formats[output]);self.assertAlmostEqual(lat,pair[0],places=6);self.assertAlmostEqual(lon,pair[1],places=6)
