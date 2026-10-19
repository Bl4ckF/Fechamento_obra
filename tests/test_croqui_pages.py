import base64
import copy
import tempfile
import unittest
from pathlib import Path
import app
import book
from drawing import clean_drawing
from book_report import book_html, photo_parts, photo_lines
from test_book import PNG
from test_app import service


class CroquiPagesTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.old=(app.DATA_DIR,app.DB)
        app.DATA_DIR=Path(self.tmp.name);app.DB=app.DATA_DIR/'fechamento.sqlite3'
        self.image=book.put_media({'data':PNG},app.DATA_DIR/'media')['ref']
        self.original=b'%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF\n'
        self.pdf=book.put_pdf({'data':base64.b64encode(self.original).decode()},app.DATA_DIR/'media')['ref']
        self.line={'id':'pdfline_10','operator_index':10,'type':'path','commands':[['M',20,30],['C',50,60,100,70,140,90]],'color':'#112233','width':1.5,'dash':'dashed','dash_array':[6,3],'dash_offset':2,'line_cap':'butt','line_join':'round'}
        self.doc={'version':1,'background_ref':self.image,'background_source':{'kind':'pdf','name':'Rede.pdf','page':1,'rotation':90,'page_width':842,'page_height':595},'pdf_source_ref':self.pdf,'pdf_lines':[self.line],'objects':[]}
        self.pages=[{'id':'page_'+str(i),'croqui':{'ref':self.image,'caption':'Folha '+str(i)},'drawing':{**copy.deepcopy(self.doc),'background_source':{**self.doc['background_source'],'page':i}}} for i in (1,3)]

    def tearDown(self):
        app.DATA_DIR,app.DB=self.old;self.tmp.cleanup()

    def test_multiple_pages_native_line_edits_roundtrip_and_backup(self):
        changed=copy.deepcopy(self.line);changed.pop('operator_index');changed.update(pdf_line_id=changed['id'],color='#ff8800',deleted=True)
        self.pages[1]['drawing']['objects']=[changed]
        raw={'croqui_pages':self.pages,'no_conductors':True}
        job=app.save_job({'work_order':'MULTI','book':raw,'services':[service()]})
        saved=job['book'];self.assertEqual(len(saved['croqui_pages']),2)
        self.assertEqual(saved['croqui_pages'][1]['drawing']['background_source']['page'],3)
        self.assertTrue(saved['croqui_pages'][1]['drawing']['objects'][0]['deleted'])
        self.assertEqual(book.normalize_book(saved,job['result']['services'],app.available_media()),saved)
        self.assertEqual(clean_drawing(saved['drawing'],app.available_media()),saved['drawing'])
        backup=app.backup_payload();self.assertEqual(len(backup['media']),2)
        for f in (app.DATA_DIR/'media').iterdir():f.unlink()
        with app.connect() as db:db.execute('DELETE FROM jobs')
        app.restore(backup)
        restored=app.records('jobs')[0]['book'];self.assertEqual(restored['croqui_pages'],saved['croqui_pages'])
        self.assertEqual((app.DATA_DIR/'media'/self.pdf).read_bytes(),self.original)
        html=book_html(job).decode();articles=html.split('<article')[1:]
        self.assertIn('Croqui da obra · 1/2',articles[0]);self.assertIn('Croqui da obra · 2/2',articles[1]);self.assertNotIn('DETALHAMENTO POR PONTO',html)

    def test_legacy_and_explicit_empty_pages(self):
        saved=book.normalize_book({'croqui':{'ref':self.image},'drawing':self.doc},[],app.available_media())
        self.assertEqual(len(saved['croqui_pages']),1)
        self.assertEqual(saved['croqui_pages'][0]['drawing']['pdf_source_ref'],self.pdf)
        saved['croqui_pages']=[]
        empty=book.normalize_book(saved,[],app.available_media());self.assertIsNone(empty['croqui']);self.assertIsNone(empty['drawing'])

    def test_pending_image_survives_normalization_and_draft_recovery(self):
        self.pages[1]['image_pending']=True
        raw={'croqui_pages':self.pages,'no_conductors':True}
        normalized=book.normalize_book(raw,[],app.available_media())
        self.assertTrue(normalized['croqui_pages'][1]['image_pending'])
        self.assertTrue(any('imagem atualizada' in item for item in normalized['pending']))
        app.automatic_draft({'draft_id':'pending-project','responsible':'Ana','book':raw,'services':[]})
        self.assertTrue(app.records('work_drafts')[0]['book']['croqui_pages'][1]['image_pending'])
        self.pages[1].pop('image_pending')
        normalized=book.normalize_book(raw,[],app.available_media())
        self.assertNotIn('image_pending',normalized['croqui_pages'][1])

    def test_invalid_pages_source_assets_and_paths(self):
        for pages in [self.pages+[self.pages[0]],self.pages*51,'wrong',[{'id':'../bad'}]]:
            with self.assertRaises(ValueError):book.normalize_book({'croqui_pages':pages},[],app.available_media())
        with self.assertRaises(ValueError):clean_drawing(self.doc,{self.image})
        for mutate in [lambda d:d['pdf_lines'][0].update(commands=[['M',0,0],['X',1,1]]),lambda d:d['pdf_lines'][0].update(id='pdfline_11'),lambda d:d['pdf_lines'][0].update(dash_array=[0,0]),lambda d:d['pdf_lines'][0].update(commands=[['M',-1,0],['L',4,4]])]:
            doc=copy.deepcopy(self.doc);mutate(doc)
            with self.assertRaises(ValueError):clean_drawing(doc)
        with self.assertRaises(ValueError):book.photo_ref(self.pdf)
        with self.assertRaises(ValueError):book.put_pdf({'data':PNG},app.DATA_DIR/'media')

    def test_photo_notes_continue_together_without_truncation(self):
        words=['palavra'+str(i) for i in range(500)]
        blocks=[('INSTALADO',' '.join(words[:180])),('DESATIVADO',' '.join(words[180:350])),('OBSERVAÇÕES',' '.join(words[350:]))]
        parts=photo_parts(blocks);self.assertGreater(len(parts),1)
        actual=' '.join(text for part in parts for _,text in part).split()
        self.assertEqual(actual,words)
        for part in parts:self.assertLessEqual(sum(2+len(text.splitlines()) for _,text in part),21)
        self.assertEqual(''.join(photo_lines('W'*100)),'W'*100)

    def test_croqui_only_draft_is_kept_in_responsible_history(self):
        app.automatic_draft({'draft_id':'only-project','responsible':'Ana','book':{'croqui_pages':self.pages},'services':[]})
        rows=app.records('work_drafts');self.assertEqual(len(rows),1);self.assertEqual(rows[0]['book']['croqui_pages'],self.pages)

if __name__=='__main__':unittest.main()
