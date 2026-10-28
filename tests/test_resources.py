import io
import unittest
from unittest.mock import patch,Mock
import resources_manager as rm

class ResourcesTests(unittest.TestCase):
 def setUp(self):
  rm._CACHE=None;rm._JOB.update(state='idle',feature=None,log=[],message='')
 def test_check_and_cache(self):
  with patch.object(rm,'probe',side_effect=[True,True,False]) as probe:
   result=rm.status();self.assertFalse(next(f for f in result['features'] if f['id']=='ocr')['ready'])
   self.assertTrue(next(f for f in result['features'] if f['id']=='poda')['ready'])
   rm.status();self.assertEqual(probe.call_count,3)
 def test_installer_allowlist_and_duplicate(self):
  for feature in ['../run.exe','pip install anything',None,[]]:
   with self.assertRaises(ValueError):rm.start(feature)
  with patch.object(rm.threading,'Thread') as thread:
   rm.start('ocr');thread.return_value.start.assert_called_once()
   with self.assertRaises(ValueError):rm.start('poda')
 def test_success_requires_validation(self):
  proc=Mock(stdout=io.StringIO('instalando\n'));proc.wait.return_value=0
  with patch.object(rm.subprocess,'Popen',return_value=proc) as popen,patch.object(rm,'checks',return_value=[{'id':'ocr','ready':False}]):
   rm._install('ocr');self.assertEqual(rm._JOB['state'],'error');self.assertNotIn('shell',popen.call_args.kwargs)
  with patch.object(rm.subprocess,'Popen',return_value=proc),patch.object(rm,'checks',return_value=[{'id':'ocr','ready':True}]):
   rm._install('ocr');self.assertEqual(rm._JOB['state'],'success')
 def test_log_bounded_and_failure(self):
  proc=Mock(stdout=io.StringIO('line\n'*200));proc.wait.return_value=1
  with patch.object(rm.subprocess,'Popen',return_value=proc),patch.object(rm,'checks',return_value=[{'id':'poda','ready':False}]):
   rm._install('poda');self.assertLessEqual(len(rm._JOB['log']),80);self.assertEqual(rm._JOB['state'],'error')
 def tearDown(self):rm._CACHE=None;rm._JOB.update(state='idle',feature=None,log=[],message='')

class ResourceHTTPTests(unittest.TestCase):
 def test_install_requires_app_token_and_invalid_features_rejected(self):
  import app,json,threading
  from urllib.request import Request,urlopen
  from urllib.error import HTTPError
  server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
  thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
  base='http://127.0.0.1:'+str(server.server_port)
  try:
   for token,code in [('wrong',403),(app.TOKEN,400)]:
    req=Request(base+'/api/resources/install',data=json.dumps({'feature':'arbitrary.exe'}).encode(),headers={'X-App-Token':token})
    with self.assertRaises(HTTPError) as error:urlopen(req)
    self.assertEqual(error.exception.code,code)
  finally:server.shutdown();server.server_close();thread.join()
