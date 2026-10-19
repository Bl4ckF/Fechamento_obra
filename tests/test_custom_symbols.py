import copy
import tempfile
import unittest
from pathlib import Path
import app
import book
from drawing import clean_drawing
from symbols import clean_symbol
from test_book import PNG
from test_app import service


def symbol():
    return {'id':'user_'+'a'*32,'name':'Chave pessoal','tag':'CH-01','color':'#123456',
            'ops':[['line',-40,0,40,0],['circle',0,0,20,False],['text',0,5,'CH',12]]}


class CustomSymbolsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.old=(app.DATA_DIR,app.DB)
        app.DATA_DIR=Path(self.tmp.name);app.DB=app.DATA_DIR/'fechamento.sqlite3'

    def tearDown(self):
        app.DATA_DIR,app.DB=self.old;self.tmp.cleanup()

    def test_revision_and_concurrent_changes(self):
        first=app.save_symbol({'symbol':symbol(),'expected_revision':0})
        changed={**first,'name':'Chave corrigida'}
        second=app.save_symbol({'symbol':changed,'expected_revision':1})
        self.assertEqual(second['revision'],2)
        with self.assertRaisesRegex(ValueError,'outra janela'):
            app.save_symbol({'symbol':first,'expected_revision':1})
        self.assertEqual(app.records('custom_symbols')[0]['name'],'Chave corrigida')

    def test_incomplete_draft_is_saved(self):
        draft={**symbol(),'name':'','ops':[]}
        saved=app.save_symbol({'symbol':draft,'expected_revision':0})
        self.assertEqual(saved['ops'],[])
        self.assertEqual(app.backup_payload()['custom_symbols'][0],saved)
        with self.assertRaises(ValueError):clean_symbol(draft)

    def test_primitive_validation(self):
        bad_ops=[['script','alert(1)'],['line',0,0,float('nan'),0],['circle',0,0,-4,False],
                 ['poly',[[1,2,3],[4,5]],False],['rect',0,0,10,10,'red'],['text',0,0,'x',1000]]
        for op in bad_ops:
            with self.subTest(op=op),self.assertRaises(ValueError):clean_symbol({**symbol(),'ops':[op]})
        for change in [{'id':'../../evil'},{'color':'url(evil)'},{'ops':[['line',0,0,2,2]]*201}]:
            with self.assertRaises(ValueError):clean_symbol({**symbol(),**change})

    def test_all_primitives_and_builtin_copies(self):
        from drawing import symbol_catalog
        for source in symbol_catalog()['symbols']:
            clean_symbol({**source,'id':symbol()['id'],'color':'#123456'})
        data={**symbol(),'ops':[['arc',0,0,10,0,180],['poly',[[-3,-4],[3,4],[1,1]],'projetado'],['rect',-5,-5,10,10,True]]}
        self.assertEqual(clean_symbol(data)['ops'],data['ops'])

    def test_embedded_definition_survives_without_library(self):
        instance={'id':'sym_a','type':'symbol','symbol_id':symbol()['id'],'symbol_definition':symbol(),
                  'x1':300,'y1':400,'size':175,'rotation':-35,'color':'#123456','label':'P7'}
        drawing={'version':1,'objects':[instance]}
        clean=clean_drawing(drawing)
        self.assertEqual(clean['objects'][0]['symbol_definition']['ops'],symbol()['ops'])
        self.assertEqual(clean_drawing(clean),clean)
        other=copy.deepcopy(instance);other['symbol_id']='user_'+'b'*32
        with self.assertRaises(ValueError):clean_drawing({'version':1,'objects':[other]})

    def test_backup_restores_library_and_placed_snapshot(self):
        saved=app.save_symbol({'symbol':symbol()})
        image=book.put_media({'data':PNG},app.DATA_DIR/'media')['ref']
        drawing={'version':1,'background_ref':image,'objects':[{'id':'sym_a','type':'symbol','symbol_id':saved['id'],
          'symbol_definition':saved,'x1':300,'y1':400,'size':70,'rotation':15,'color':'#123456'}]}
        job=app.save_job({'work_order':'TEST-CUSTOM','services':[service()],
                         'book':{'croqui':{'ref':image},'drawing':drawing}})
        backup=app.backup_payload()
        with app.connect() as db:db.execute('DELETE FROM custom_symbols');db.execute('DELETE FROM jobs')
        app.restore(backup)
        self.assertEqual(app.records('custom_symbols'),[saved])
        self.assertEqual(app.records('jobs')[0]['book'],job['book'])
        app.save_symbol({'symbol':{**saved,'ops':[['line',0,0,20,20]]},'expected_revision':1})
        self.assertEqual(app.records('jobs')[0]['book']['drawing']['objects'][0]['symbol_definition']['ops'],saved['ops'])

    def test_invalid_backup_does_not_write_symbols(self):
        saved=app.save_symbol({'symbol':symbol()})
        backup=app.backup_payload();backup['custom_symbols'].append({**symbol(),'id':'invalid'})
        with self.assertRaises(ValueError):app.restore(backup)
        self.assertEqual(app.records('custom_symbols'),[saved])


if __name__=='__main__':unittest.main()
