import io
import json
import tempfile
import threading
import unittest
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from PIL import Image
import app
from poda import routes

class PodaIntegrationTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.old=routes._CORE;routes._CORE=None
  cls.core=routes.core(cls.tmp.name)
  cls.server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
  cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
  cls.base='http://127.0.0.1:'+str(cls.server.server_port)
 @classmethod
 def tearDownClass(cls):
  cls.server.shutdown();cls.server.server_close();cls.thread.join();routes._CORE=cls.old;cls.tmp.cleanup()
 def get(self,path):
  with urlopen(self.base+path) as r:return r.read()
 def post(self,path,data,token=app.TOKEN,kind='application/json'):
  raw=json.dumps(data).encode() if kind=='application/json' else data
  req=Request(self.base+path,data=raw,headers={'X-App-Token':token,'Content-Type':kind})
  with urlopen(req) as r:return json.load(r)
 def test_home_and_namespaced_security(self):
  self.assertIn(b'PODA',self.get('/'));self.assertIn(b'FECHAMENTO',self.get('/'))
  self.assertIn(b'Fechamento de obras',self.get('/fechamento'))
  self.assertIn(b'Novo Book',self.get('/poda/'))
  with self.assertRaises(HTTPError) as e:self.post('/poda/api/draft',{},token='wrong')
  self.assertEqual(e.exception.code,403)
  for route in ['/poda/assets/../book_engine.py','/poda/api/update/install']:
   with self.assertRaises(HTTPError):self.get(route)
 def test_draft_isolated_and_reloaded(self):
  before=self.get('/api/working-drafts')
  self.post('/poda/api/draft',{'os':'PODA-TESTE','records':[]})
  self.assertEqual(json.loads(self.get('/poda/api/draft'))['os'],'PODA-TESTE')
  self.assertEqual(self.get('/api/working-drafts'),before)
 def test_generate_edit_and_preserve_photos(self):
  image=io.BytesIO();Image.new('RGB',(80,60),'green').save(image,'PNG')
  photo=self.post('/poda/api/upload',image.getvalue(),kind='image/png')['url']
  row={'coord':'-20.47, -54.62','antes':photo,'depois':photo,'rua':'Teste','bairro':'Centro'}
  job=self.post('/poda/api/books/generate',{'os':'123456','date':'21/10/2026','qtd':1,'records':[row]})
  self.assertTrue(self.get(job['pdf_url']).startswith(b'%PDF'))
  ident=job['id'];saved=json.loads(self.get('/poda/api/books/'+str(ident)))
  self.assertEqual(saved['payload']['records'][0]['rua'],'Teste')
  photo_url=f'/poda/api/books/{ident}/photo/0/antes'
  self.assertTrue(self.get(photo_url).startswith(b'\x89PNG'))
  edited=self.post(f'/poda/api/books/{ident}/edit',{'os':'123456','date':'21/10/2026','qtd':2,'records':[{**row,'antes':photo_url,'depois':f'/poda/api/books/{ident}/photo/0/depois'}]})
  self.assertTrue(self.get(edited['pdf_url']).startswith(b'%PDF'))
  self.assertEqual(json.loads(self.get('/poda/api/books/'+str(ident)))['qtd'],2)
  from pathlib import Path
  self.assertTrue(Path(edited['backup']).exists())
 def test_faixa_pdf(self):
  image=io.BytesIO();Image.new('RGB',(30,30),'orange').save(image,'PNG')
  photo=self.post('/poda/api/upload',image.getvalue(),kind='image/png')['url']
  job=self.post('/poda/api/books/generate',{'book_type':'limpeza_faixa','unit':'m2','os':'654321','date':'21/10/2026','qtd':'12.5','records':[{'coord':'-20.47,-54.62','measure':'12.5','antes':photo,'depois':photo}]})
  self.assertTrue(self.get(job['pdf_url']).startswith(b'%PDF'))
