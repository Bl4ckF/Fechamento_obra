import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import app
import job_files
from book import put_media
from test_app import service


class JobFolderTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.data=patch.object(app,'DATA_DIR',self.root);self.db=patch.object(app,'DB',self.root/'fechamento.sqlite3')
        self.data.start();self.db.start()
    def tearDown(self):
        self.db.stop();self.data.stop();self.tmp.cleanup()
    def payload(self):
        photo=put_media({'name':'Foto.png','data':'iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB'},self.root/'media')
        row=service();row['point_id']='p1';row['entry_id']='entry1'
        return {'work_order':'../CON:Obra?*','responsible':'Equipe','date':'2026-10-20','services':[row],
                'book':{'points':[{'id':'p1','number':'1/2','photos':[dict(photo,stage='Depois',caption='Registro de teste')]}],
                        'conductors':[],'no_conductors':True,'croqui':None}}
    def test_creates_offline_book_and_photo_folder_under_data(self):
        job=app.save_job(self.payload());folder=Path(job['folder'])
        self.assertTrue(folder.resolve().is_relative_to(self.root.resolve()))
        self.assertTrue((folder/'book.html').is_file());self.assertTrue((folder/'mao_de_obra_e_materiais.csv').is_file())
        photos=json.loads((folder/'fotos/index.json').read_text());self.assertEqual(len(photos),1)
        self.assertEqual((folder/photos[0]['file']).read_bytes(),(self.root/'media'/photos[0]['source']).read_bytes())
        html=(folder/'book.html').read_text();self.assertNotIn('/media/',html);self.assertNotIn('src="/assets/',html)
        self.assertIn('fotos/',html);self.assertIn('recursos/book-print.css',html)
        self.assertEqual(json.loads((folder/'registro.json').read_text())['job']['id'],job['id'])
    def test_edit_creates_new_revision_and_preserves_original(self):
        first=app.save_job(self.payload());original=(Path(first['folder'])/'registro.json').read_bytes()
        payload=self.payload();payload['source_job_id']=first['id'];payload['services'][0]['quantity']='6'
        second=app.save_job(payload)
        self.assertNotEqual(first['folder'],second['folder']);self.assertEqual(second['source_job_id'],first['id'])
        self.assertEqual((Path(first['folder'])/'registro.json').read_bytes(),original)
        self.assertEqual(len(app.records('jobs')),2)
    def test_removes_136_credit_from_archived_html_without_changing_job_or_photos(self):
        job=app.save_job(self.payload());folder=Path(job['folder'])
        original=(folder/'registro.json').read_bytes()
        photo_files={p:p.read_bytes() for p in (folder/'fotos').rglob('*') if p.is_file()}
        reports=('book.html','mao_de_obra_e_materiais.html')
        originals={}
        for name in reports:
            report=folder/name;html=report.read_text()
            self.assertNotIn('class="developer-watermark"',html)
            self.assertNotIn('class="developer-credit"',html)
            originals[name]=html
            report.write_text(html.replace('</article>','<div class="developer-watermark">Desenvolvido por Matheus Alves Araújo</div><small class="developer-credit">Desenvolvido por Matheus Alves Araújo<br>matheusalvesaraujo540@gmail.com</small></article>'),encoding='utf-8')
        app.ensure_job_folder(job)
        for name,html in originals.items():self.assertEqual((folder/name).read_text(),html)
        self.assertEqual((folder/'registro.json').read_bytes(),original)
        for p,data in photo_files.items():self.assertEqual(p.read_bytes(),data)
    def test_open_folder_only_uses_saved_record_and_allowed_section(self):
        job=app.save_job(self.payload())
        with patch('job_files.open_folder',return_value=True) as opened:
            result=app.open_job_folder({'id':job['id'],'section':'photos'})
            self.assertTrue(result['opened']);self.assertEqual(opened.call_args.args[0],Path(job['folder'])/'fotos')
        with self.assertRaises(ValueError):app.open_job_folder({'id':job['id'],'section':'../../'})
        with self.assertRaises(ValueError):app.open_job_folder({'id':'../../outro'})
    def test_windows_reserved_names_and_separators(self):
        self.assertEqual(job_files.safe_name('CON'),'_CON')
        self.assertNotIn('/',job_files.safe_name('../a/b'))
        self.assertNotIn(':',job_files.safe_name('C:\\Users\\foo'))

if __name__=='__main__':unittest.main()
