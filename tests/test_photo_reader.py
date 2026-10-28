import base64
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
import photo_reader as reader

TEXT='Obra: 123456\nPonto: 07\n21K 753302 7725693\n21/10/2026 14:30:00\nRua Afonso Pena\nANTES'
class PhotoReaderTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
  image=io.BytesIO();Image.new('RGB',(120,80),'green').save(image,'JPEG');self.binary=image.getvalue()
 def tearDown(self):self.tmp.cleanup()
 def analyze(self,text=TEXT):
  with patch.object(reader,'run_ocr',return_value=(text,[.99],[])):
   return reader.analyze({'name':'foto.jpg','data':base64.b64encode(self.binary).decode()},self.root)
 def test_extract_and_missing_not_invented(self):
  fields=reader.extract_fields(TEXT)
  self.assertEqual(fields['work_order'],'123456');self.assertEqual(fields['point'],'07');self.assertEqual(fields['stage'],'Antes')
  self.assertEqual(fields['coordinate'],'21K 753302 7725693')
  self.assertEqual(reader.extract_fields('21K7533027725693')['coordinate'],'21K 753302 7725693')
  self.assertEqual(reader.extract_fields('21K753302772569')['coordinate'],'')
  empty=reader.extract_fields('árvore poste rua qualquer')
  self.assertEqual(empty['work_order'],'');self.assertEqual(empty['point'],'');self.assertEqual(empty['coordinate'],'')
 def test_organize_preserves_original_and_repeat(self):
  result=self.analyze();photo={**result['suggested'],'id':result['id']}
  payload={'confirmed':True,'photos':[photo]}
  before=reader.read_record(result['id'],self.root)[1].read_bytes()
  first=reader.organize(payload,self.root);second=reader.organize(payload,self.root)
  self.assertNotEqual(first['path'],second['path'])
  self.assertEqual((Path(first['path'])/first['photos'][0]['photo']).read_bytes(),before)
  self.assertEqual(reader.read_record(result['id'],self.root)[1].read_bytes(),before)
  self.assertTrue((Path(first['path'])/'indice.json').is_file())
 def test_reject_unreviewed_missing_data_and_tamper(self):
  result=self.analyze();photo={**result['suggested'],'id':result['id']}
  for payload in [{'photos':[photo]},{'confirmed':True,'photos':[{**photo,'point':''}]},{'confirmed':True,'photos':[{**photo,'coordinate':'','location':''}]}]:
   with self.assertRaises(ValueError):reader.organize(payload,self.root)
  reader.read_record(result['id'],self.root)[1].write_bytes(b'tampered')
  with self.assertRaisesRegex(ValueError,'alterada'):reader.organize({'confirmed':True,'photos':[photo]},self.root)
 def test_paths_conflict_and_no_arbitrary_read(self):
  self.assertNotEqual(reader.safe_folder('A/B'),reader.safe_folder('A:B'))
  self.assertNotIn('/',reader.safe_folder('../../CON: obra'))
  with self.assertRaises(ValueError):reader.read_record('../outside',self.root)
  with self.assertRaises(ValueError):reader.open_folder({'folder':'../../'},self.root)
 def test_exif_conflict(self):
  metadata={'lat':-23.5,'lon':-46.6,'decimal':'-23.5,-46.6','utm':'23K 336692 7400132'}
  with patch.object(reader,'exif_info',return_value=metadata):r=self.analyze()
  self.assertEqual(r['suggested']['coordinate'],'')
  self.assertTrue(any('divergem' in s for s in r['warnings']))
 def test_import_work_guard(self):
  r=self.analyze();photo={**r['suggested'],'id':r['id']}
  with self.assertRaises(ValueError):reader.book_photos({'confirmed':True,'work_order':'OUTRA','photos':[photo]},self.root)
  result=reader.book_photos({'confirmed':True,'work_order':'123456','photos':[photo]},self.root)
  self.assertTrue((self.root/'media'/result['photos'][0]['photo']['ref']).is_file())
 def test_no_ocr_allows_manual_fields(self):
  r=self.analyze('')
  self.assertEqual(r['suggested']['work_order'],'')
  self.assertTrue(r['warnings'])
 def test_reject_invalid_upload(self):
  with self.assertRaises(ValueError):reader.analyze({'data':base64.b64encode(b'notimage').decode()},self.root)

class PhotoGroupingTests(unittest.TestCase):
 def row(self,n,meters,work='123',point=''):
  # Equator: longitude degree is about 111195 m.
  return {'id':f'{n:032x}','work_order':work,'point':point,'coordinate':f'0, {meters/111195}'}
 def test_anchor_radius_no_chain(self):
  rows=[self.row(1,0),self.row(2,20),self.row(3,40)]
  result=reader.group_photos({'radius_m':25,'photos':rows})
  self.assertEqual([len(g['ids']) for g in result['groups']],[2,1])
  self.assertTrue(all(g['max_distance_m']<=25 for g in result['groups']))
  self.assertEqual(result,reader.group_photos({'radius_m':25,'photos':list(reversed(rows))}))
  self.assertEqual(len(reader.group_photos({'radius_m':50,'photos':rows})['groups']),1)
 def test_other_work_missing_and_conflicting_points(self):
  rows=[self.row(1,0,point='1'),self.row(2,1,point='2'),self.row(3,1,work='999'),{**self.row(4,2),'coordinate':''}]
  result=reader.group_photos({'radius_m':25,'photos':rows})
  self.assertEqual(len(result['groups']),2);self.assertEqual(len(result['excluded']),1)
  self.assertTrue(result['groups'][0]['conflict']);self.assertEqual(result['groups'][0]['point'],'')
 def test_invalid_and_limits(self):
  for radius in [0,501,'invalid',float('nan'),float('inf'),True]:
   with self.assertRaises(ValueError):reader.group_photos({'radius_m':radius,'photos':[self.row(1,0)]})
  with self.assertRaises(ValueError):reader.group_photos({'photos':[self.row(1,0)]*2})
 def test_same_point_far_apart_requires_review(self):
  groups=reader.group_photos({'radius_m':25,'photos':[self.row(1,0,point='1'),self.row(2,90,point='1')]})['groups']
  self.assertTrue(all(g['conflict'] for g in groups))

class ZipAddressTests(unittest.TestCase):
 def zip_data(self,files):
  import zipfile
  out=io.BytesIO()
  with zipfile.ZipFile(out,'w') as z:
   for name,data in files:z.writestr(name,data)
  return {'data':base64.b64encode(out.getvalue()).decode()}
 def test_zip_nested_and_invalid_image(self):
  out=io.BytesIO();Image.new('RGB',(20,20)).save(out,'PNG')
  with tempfile.TemporaryDirectory() as tmp,patch.object(reader,'run_ocr',return_value=(TEXT,[],[])):
   result=reader.analyze_zip(self.zip_data([('pasta/foto.png',out.getvalue()),('bad.jpg',b'bad'),('nota.txt',b'text')]),tmp)
   self.assertEqual(len(result['photos']),1);self.assertEqual(len(result['errors']),1)
 def test_zip_traversal_and_capacity(self):
  for files in [[('../foto.jpg',b'a')],[('/foto.jpg',b'a')]]:
   with self.assertRaises(ValueError):reader.analyze_zip(self.zip_data(files),'unused')
  with self.assertRaises(ValueError):reader.analyze_zip({**self.zip_data([('a.jpg',b'a'),('b.jpg',b'a')]),'available':1},'unused')
 def test_address_equivalence_and_numbers_preserved(self):
  rows=[{'id':f'{i:032x}','work_order':work,'location':address} for i,(work,address) in enumerate([('1','Av. São José, 10 - Campo Grande'),('1','Avenida Sao Jose 10 Campo Grande'),('1','Av. São José, 11 - Campo Grande'),('2','Av. São José, 10 - Campo Grande')],1)]
  result=reader.group_photos({'mode':'address','photos':rows});self.assertEqual(sorted(len(g['ids']) for g in result['groups']),[1,1,2])
  self.assertEqual(result['excluded'],[])
 def test_address_only_organize_and_import_no_invented_gps(self):
  with tempfile.TemporaryDirectory() as tmp,patch.object(reader,'run_ocr',return_value=('Obra: 1\nPonto: 2\nRua Teste 10',[],[])):
   image=io.BytesIO();Image.new('RGB',(20,20)).save(image,'PNG')
   result=reader.analyze({'name':'foto.png','data':base64.b64encode(image.getvalue()).decode()},tmp)
   photo={**result['suggested'],'id':result['id']}
   organized=reader.organize({'confirmed':True,'photos':[photo]},tmp)
   self.assertIsNone(organized['photos'][0]['lat'])
   imported=reader.book_photos({'confirmed':True,'work_order':'1','photos':[photo]},tmp)
   self.assertEqual(imported['photos'][0]['coordinate'],'')
