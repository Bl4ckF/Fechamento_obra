import base64
import gc
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import app
import programs


class IntegratedOperationsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.patches=[patch.object(app,'DATA_DIR',self.root/'dados'),patch.object(app,'DB',self.root/'dados'/'test.sqlite3'),patch.object(app,'ROOT',self.root)]
        for value in self.patches:value.start()
        self.server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.base='http://127.0.0.1:'+str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join()
        for value in reversed(self.patches):value.stop()
        gc.collect()
        self.temp.cleanup()

    def request(self,path,data=None,token=app.TOKEN):
        request=Request(self.base+path,data=json.dumps(data).encode() if data is not None else None,
                        headers={'Content-Type':'application/json','X-App-Token':token})
        return urlopen(request,timeout=5)

    def test_documents_persist_with_draft_and_survive_backup_restore(self):
        data={'operation':'cadcraft','context':'draft-a','name':'rede.dxf','data':base64.b64encode(b'0\nEOF\n').decode()}
        with self.request('/api/operation-documents',data) as response:self.assertTrue(json.load(response)['saved'])
        with self.request('/api/operation-documents?context=draft-b&operation=cadcraft') as response:self.assertEqual(json.load(response),[])
        backup=app.backup_payload()
        self.assertEqual(len(backup['operation_documents']),1)
        with app.connect() as db:db.execute('DELETE FROM operation_documents')
        app.restore(backup)
        self.assertEqual(app.records('operation_documents')[0]['name'],'rede.dxf')

    def test_documents_require_token_and_reject_paths_and_external_commands(self):
        with self.assertRaises(HTTPError) as caught:self.request('/api/operation-documents',{},token='invalid')
        self.assertEqual(caught.exception.code,403);caught.exception.close()
        for operation,name in [('cmd','documento'),('pdfcraft','../outside.pdf')]:
            with self.assertRaises(ValueError):programs.normalize_document({'operation':operation,'context':'draft-a','name':name,'data':'YQ=='})

    def test_embedded_page_has_scoped_csp_and_bridge(self):
        module=self.root/'web'/'operations'/'pdfcraft';module.mkdir(parents=True)
        (module/'index.html').write_text('<html><head><script type="module">console.log(1)</script></head></html>',encoding='utf8')
        (module/'engine.wasm').write_bytes(b'\x00asm')
        with self.request('/operations/pdfcraft/index.html') as response:
            policy=response.headers['Content-Security-Policy']
            self.assertIn("frame-ancestors 'self'",policy)
            self.assertIn("'sha256-",policy)
            self.assertIn(b'/operations-bridge.js',response.read())
        self.assertTrue(next(item for item in programs.catalog(self.root) if item['id']=='pdfcraft')['available'])

    def test_catalog_ignores_desktop_executables(self):
        project=self.root/'installation'/'Fechamento_obra';project.mkdir(parents=True)
        desktop=project.parent/'apps'/'CADCraft';desktop.mkdir(parents=True)
        (desktop/'cadcraft.exe').write_bytes(b'not an executable')
        cad=next(item for item in programs.catalog(project) if item['id']=='cadcraft')
        self.assertFalse(cad['available'])
        self.assertEqual(cad['url'],'/operations/cadcraft/index.html?host=parent')


if __name__=='__main__':unittest.main()
