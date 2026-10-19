import copy
import importlib
import json
import os
import tempfile
import threading
import unittest
from decimal import Decimal
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import engine

TMP=tempfile.TemporaryDirectory()
os.environ['ENGELMIG_DATA_DIR']=TMP.name
import app

def service(labor_id='s1r4',quantity='3',coefficient='2',movement='instalado'):
    return {'labor_id':labor_id,'quantity':quantity,'materials':[{'material_id':'m2','coefficient':coefficient,'unit':'PC','movement':movement}], 'reviewed':True,'no_materials':False,'variant':'Exemplo de teste; não usar em obra'}

class DomainTests(unittest.TestCase):
    def test_preserves_source_rows_and_missing_values(self):
        self.assertEqual(len(engine.MATERIALS),2652)
        self.assertEqual(len(engine.LABOR),733)
        self.assertEqual(sum(not m['unit'] for m in engine.MATERIALS.values()),1)
        self.assertNotIn('m77',engine.MATERIALS)
        self.assertEqual(engine.LABOR['s1r280']['us_source'],'#REF!')
        self.assertIsNone(engine.LABOR['s1r280']['us'])

    def test_n1_suggestions_have_evidence_and_real_catalog_ids(self):
        result=engine.suggestions('s1r4')
        groups={g['name']:g for g in result['groups']}
        for family in ['Cruzetas','Pinos','Isoladores']:
            self.assertIn(family,groups)
            self.assertTrue(groups[family]['material_ids'])
            self.assertTrue(groups[family]['evidence'])
            self.assertTrue(all(k in engine.MATERIALS for k in groups[family]['material_ids']))
        self.assertNotIn('Postes',groups)
        self.assertNotIn('Cabos e condutores',groups)
        self.assertNotIn('coefficient',json.dumps(result))

    def test_full_catalog_suggestion_coverage_does_not_crash(self):
        for lid in engine.LABOR:
            result=engine.suggestions(lid)
            for group in result['groups']:
                self.assertTrue(group['evidence'])
                self.assertEqual(len(group['material_ids']),group['total'])

    def test_independent_operations_same_code(self):
        self.assertEqual(engine.LABOR['s1r4']['code'],engine.LABOR['s1r6']['code'])
        self.assertNotEqual(engine.LABOR['s1r4']['operation'],engine.LABOR['s1r6']['operation'])
        result=engine.calculate([service(),service('s1r6','1','1','desativado')])
        totals={r['movement']:r['quantity'] for r in result['materials']}
        self.assertEqual(totals,{'instalado':'6','desativado':'1'})

    def test_sleeves_do_not_include_protective_gloves_and_retrieval_uses_detail(self):
        sleeves=engine.FAMILY_MATERIALS['Emendas']
        self.assertFalse(any('LUVA BORR' in engine.MATERIAL_NORM[mid] for mid in sleeves))
        names={g['name'] for g in engine.suggestions('s1r52')['groups']}
        self.assertIn('Cordoalhas',names)
        names={g['name'] for g in engine.suggestions('s1r451')['groups']}
        self.assertIn('Cabos e condutores',names)

    def test_decimal_aggregation_and_recalculation(self):
        result=engine.calculate([service(quantity='0,1',coefficient='0,2'),service(quantity='0.1',coefficient='0.2')])
        self.assertEqual(result['materials'][0]['quantity'],'0.04')
        self.assertTrue(result['ready'])
        changed=engine.calculate([service(quantity='4',coefficient='2')])
        self.assertEqual(changed['materials'][0]['quantity'],'8')

    def test_no_materials_requires_explicit_review(self):
        s=service();s['materials']=[]
        with self.assertRaises(ValueError):engine.calculate([s])
        s['no_materials']=True
        self.assertTrue(engine.calculate([s])['ready'])
        s['reviewed']=False
        self.assertFalse(engine.calculate([s])['ready'])

    def test_bad_quantities_and_missing_unit_do_not_become_zero(self):
        for value in ['',0,-1,'NaN','Infinity','1e30','0.0000001']:
            with self.assertRaises(ValueError,msg=str(value)):engine.calculate([service(quantity=value)])
        s=service();missing=next(m for m in engine.MATERIALS.values() if not m['unit'] and m['code'])
        s['materials'][0].update(material_id=missing['id'],unit='')
        with self.assertRaises(ValueError):engine.calculate([s])
        s['materials'][0]['unit']='UN'
        self.assertEqual(engine.calculate([s])['materials'][0]['unit'],'UN')

    def test_missing_code_blocks_completion_and_unit_conflicts(self):
        r=engine.calculate([service('s1r280')]);self.assertFalse(r['ready']);self.assertEqual(r['us_missing'],1)
        s=service();s['materials'][0]['material_id']='m77'
        with self.assertRaises(ValueError):engine.calculate([s])
        missing=next(m for m in engine.MATERIALS.values() if not m['unit'] and m['code'])
        a=service();a['materials'][0].update(material_id=missing['id'],unit='UN')
        b=copy.deepcopy(a);b['materials'][0]['unit']='PC'
        self.assertFalse(engine.calculate([a,b])['ready'])

    def test_preserve_catalog_unit(self):
        s=service();s['materials'][0]['unit']='M'
        self.assertEqual(engine.calculate([s])['materials'][0]['unit'],'PC')

class StorageTests(unittest.TestCase):
    def setUp(self):
        with app.connect() as db:db.execute('DELETE FROM profiles');db.execute('DELETE FROM jobs')

    def test_snapshots_and_backup_restore(self):
        payload={'work_order':'TESTE','services':[service()],'status':'fechado'}
        j=app.save_job(payload)
        payload['services'][0]['quantity']='7'
        app.save_job(payload)
        old=next(x for x in app.records('jobs') if x['id']==j['id'])
        self.assertEqual(old['result']['materials'][0]['quantity'],'6')
        self.assertEqual(len(app.records('jobs')),2)
        profile=engine.clean_profile(service());profile.update(id='test',updated_at=app.now());app.save_record('profiles',profile)
        backup={'app':app.APP_ID,'schema':1,'profiles':app.records('profiles'),'jobs':app.records('jobs')}
        result=app.restore(backup);self.assertEqual(result,{'profiles':1,'jobs':2})
        self.assertTrue(list((Path(TMP.name)/'backups').glob('*.sqlite3')))
        bad=copy.deepcopy(backup);bad['jobs'][0]['result']['services'][0]['quantity']='-1'
        with self.assertRaises(ValueError):app.restore(bad)
        self.assertEqual(len(app.records('jobs')),2)

    def test_close_gate_and_csv_roundtrip(self):
        s=service();s['reviewed']=False
        with self.assertRaises(ValueError):app.save_job({'work_order':'X','services':[s],'status':'fechado'})
        draft=app.save_job({'work_order':'=1+1','services':[s],'status':'rascunho'})
        text=app.report_csv(draft).decode('utf-8-sig')
        self.assertIn("'=1+1",text)
        self.assertIn('PENDÊNCIAS',text)
        self.assertIn('instalado'.upper(),text)

class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.base=f'http://127.0.0.1:{cls.server.server_port}'
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.thread.join()
    def test_pdf_modules_mime_policy_and_form_default(self):
        for path,kind in [('/symbol-editor.js','text/javascript'),('/drawing-transform.js','text/javascript'),('/croqui-render-worker.js','text/javascript'),('/croqui-render.js','text/javascript'),('/pdf-search.js','text/javascript'),('/croqui-pages.js','text/javascript'),('/croqui-pdf-export.js','text/javascript'),('/vendor/pdf-lib/pdf-lib.min.js','text/javascript'),('/drawing-ui.js','text/javascript'),('/pdf-lines.js','text/javascript'),('/pdf-source.js','text/javascript'),('/croqui-quality.js','text/javascript'),('/pdf-text.js','text/javascript'),('/network-symbols.js','text/javascript'),('/pdf-background.js','text/javascript'),('/records-sync.js','text/javascript'),('/vendor/pdfjs/pdf.min.mjs','text/javascript'),('/vendor/pdfjs/pdf.worker.min.mjs','text/javascript'),('/vendor/pdfjs/standard_fonts/FoxitSerif.pfb','application/octet-stream'),('/vendor/pdfjs/standard_fonts/LiberationSans-Regular.ttf','font/ttf')]:
            with urlopen(self.base+path) as response:
                self.assertIn(kind,response.headers['Content-Type']);self.assertGreater(len(response.read()),100)
                self.assertIn("worker-src 'self'",response.headers['Content-Security-Policy'])
        with urlopen(self.base+'/api/settings') as response:
            config=json.load(response);self.assertIn('forms.cloud.microsoft/Pages/ResponsePage.aspx?',config['forms_url'])
            self.assertEqual(config['sync_branch'],'registros-materiais')
    def test_custom_symbols_autosave_through_http(self):
        with urlopen(self.base+'/api/bootstrap') as r:boot=json.load(r)
        definition={'id':'user_'+'c'*32,'name':'Chave HTTP','color':'#123456','ops':[['line',0,0,20,20]]}
        payload={'symbol':definition,'expected_revision':0}
        request=Request(self.base+'/api/custom-symbols',data=json.dumps(payload).encode(),headers={'X-App-Token':boot['token']},method='POST')
        with urlopen(request) as response:saved=json.load(response)
        self.assertEqual(saved['revision'],1)
        with urlopen(self.base+'/api/custom-symbols') as response:self.assertIn(saved,json.load(response))
        with urlopen(self.base+'/api/bootstrap') as response:self.assertIn(saved,json.load(response)['custom_symbols'])
        request=Request(self.base+'/api/custom-symbols',data=json.dumps(payload).encode(),method='POST')
        with self.assertRaises(HTTPError) as error:urlopen(request)
        self.assertEqual(error.exception.code,403)

    def test_source_pdf_upload_read_and_backup_through_http(self):
        import base64
        with urlopen(self.base+'/api/bootstrap') as r:boot=json.load(r)
        content=b'%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF\n'
        req=Request(self.base+'/api/project-pdf',data=json.dumps({'name':'Projeto.pdf','data':base64.b64encode(content).decode()}).encode(),headers={'X-App-Token':boot['token']},method='POST')
        with urlopen(req) as r:stored=json.load(r)
        with urlopen(self.base+'/media/'+stored['ref']) as r:
            self.assertEqual(r.headers['Content-Type'],'application/pdf');self.assertEqual(r.read(),content)
        with urlopen(self.base+'/api/backup') as r:backup=json.load(r)
        self.assertTrue(any(item['ref']==stored['ref'] for item in backup['media']))

    def test_coordinate_format_and_symbol_catalog_through_http(self):
        with urlopen(self.base+'/api/coordinate?q=-20.47,-54.62') as r:data=json.load(r)
        self.assertTrue(data['utm'].startswith('21K '))
        self.assertEqual(data['lat'],-20.47)
        with urlopen(self.base+'/api/bootstrap') as r:data=json.load(r)
        self.assertEqual(data['version'],app.VERSION)
        self.assertGreater(len(data['network_symbols']['symbols']),100)

    def test_automatic_learning_and_draft_recovery_through_http(self):
        with urlopen(self.base+'/api/bootstrap') as r:boot=json.load(r)
        def post(path,value):
            request=Request(self.base+path,data=json.dumps(value).encode(),headers={'X-App-Token':boot['token']},method='POST')
            with urlopen(request) as r:return json.load(r)
        editor={**service('s1r52'),'entry_id':'http-entry','reviewed':False,'variant':'QA automático'}
        saved=post('/api/draft',{'draft_id':'QA-HTTP-DRAFT','work_order':'QA-AUTO','responsible':'QA Responsável','services':[],'editor':editor,'editor_touched':True})
        self.assertEqual(saved['learning']['changed'],1)
        selected=post('/api/learning/select',{'labor_id':'s1r52','responsible':'QA Responsável'})
        self.assertEqual(selected['editor']['materials'][0]['coefficient'],'2')
        with urlopen(self.base+'/api/working-drafts') as r:self.assertTrue(any(d['work_order']=='QA-AUTO' for d in json.load(r)))
        with urlopen(self.base+'/api/learning/publish') as r:
            shared=json.load(r);self.assertNotIn('QA Responsável',json.dumps(shared,ensure_ascii=False))
        with urlopen(self.base+'/api/learning/export') as r:exported=json.load(r)
        self.assertEqual(post('/api/learning/import',exported)['imported'],0)
        for path in ['/drawing.js','/learning.js','/v4.css']:
            with urlopen(self.base+path) as r:self.assertGreater(len(r.read()),100)
    def test_clear_draft_through_http_blocks_late_autosave(self):
        with urlopen(self.base+'/api/bootstrap') as r:boot=json.load(r)
        def post(path,value,token=boot['token']):
            req=Request(self.base+path,data=json.dumps(value).encode(),headers={'X-App-Token':token},method='POST')
            with urlopen(req) as r:return json.load(r)
        payload={'draft_id':'clear-http','work_order':'Apagar QA','services':[]}
        post('/api/draft',payload)
        with self.assertRaises(HTTPError) as error:post('/api/draft-clear',payload,token='invalid')
        self.assertEqual(error.exception.code,403)
        blank=post('/api/draft-clear',{'draft_id':payload['draft_id'],'date':'2026-10-15'})['draft']
        with self.assertRaises(HTTPError) as error:post('/api/draft',payload)
        self.assertEqual(error.exception.code,400)
        with urlopen(self.base+'/api/bootstrap') as r:current=json.load(r)
        self.assertEqual(current['draft'],blank)
        self.assertIn('clear-http',current['cleared_draft_ids'])
        with urlopen(self.base+'/api/working-drafts') as r:
            self.assertFalse(any(d['draft_id']=='clear-http' for d in json.load(r)))

    def test_book_media_report_draft_and_map_through_http(self):
        with urlopen(self.base+'/api/bootstrap') as r:boot=json.load(r)
        def post(path,value):
            req=Request(self.base+path,data=json.dumps(value).encode(),headers={'X-App-Token':boot['token']},method='POST')
            with urlopen(req) as r:return json.load(r)
        photo=post('/api/media',{'name':'teste.png','data':'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j9oUAAAAASUVORK5CYII='})
        with urlopen(self.base+'/media/'+photo['ref']) as r:self.assertTrue(r.read().startswith(b'\x89PNG'))
        book={'points':[{'id':'p1','number':'1','coordinate':'-20.47, -54.62','photos':[photo]}],'croqui':photo,'no_conductors':True}
        payload={'work_order':'QA HTTP v3','book':book,'services':[dict(service(),point_id='p1')],'status':'fechado'}
        checked=post('/api/book-check',payload);self.assertTrue(checked['ready'])
        job=post('/api/job',payload);self.assertEqual(job['workflow'],'aguardando_forms')
        with urlopen(self.base+'/book?id='+job['id']) as r:
            report=r.read().decode();self.assertIn('CROQUI DA OBRA',report);self.assertIn(photo['ref'],report)
        with urlopen(self.base+'/materials-report?id='+job['id']) as r:
            report=r.read().decode();self.assertIn('MÃO DE OBRA E MATERIAIS',report);self.assertIn('Total de mãos de obra',report);self.assertNotIn('Composição do serviço',report)
        with urlopen(self.base+'/api/export?id='+job['id']) as r:
            self.assertIn('mao_de_obra_e_materiais_',r.headers['Content-Disposition'])
            self.assertIn('MATERIAIS POR MÃO DE OBRA',r.read().decode('utf-8-sig'))
        with urlopen(self.base+'/api/summary?id='+job['id']) as r:self.assertIn('PONTO 1',json.load(r)['text'])
        post('/api/draft',payload)
        with urlopen(self.base+'/api/bootstrap') as r:self.assertEqual(json.load(r)['draft']['work_order'],'QA HTTP v3')
        with urlopen(self.base+'/map_v11.html') as r:self.assertIn("frame-ancestors 'self'",r.headers['Content-Security-Policy'])
        for path in ['/book.js','/book.css','/book-print.css','/book-print.js','/assets/engelmig.png','/qfield_manifest.js','/qfield_tiles/t_-2736_-1035.js']:
            with urlopen(self.base+path) as r:self.assertEqual(r.status,200);r.read()
        with urlopen(self.base+'/api/backup') as r:backup=json.load(r)
        self.assertTrue(any(m['ref']==photo['ref'] for m in backup['media']))
        restored=post('/api/restore',backup);self.assertGreaterEqual(restored['media'],1)

    def test_large_lossless_croqui_upload_through_http(self):
        import base64,struct,zlib
        from book import media_bytes
        # PNG válido com metadados grandes: ultrapassa os limites antigos de
        # 8 MB por imagem e de 25 MB por requisição JSON/base64.
        png=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j9oUAAAAASUVORK5CYII=')
        payload=b'Description\0'+b'A'*20_000_000;chunk=b'tEXt'+payload
        binary=png[:-12]+struct.pack('>I',len(payload))+chunk+struct.pack('>I',zlib.crc32(chunk))+png[-12:]
        with urlopen(self.base+'/api/bootstrap') as r:boot=json.load(r)
        request=Request(self.base+'/api/media',data=json.dumps({'name':'Croqui.png','data':'data:image/png;base64,'+base64.b64encode(binary).decode()}).encode(),headers={'X-App-Token':boot['token']},method='POST')
        with urlopen(request) as r:photo=json.load(r)
        self.assertEqual(photo['size'],len(binary));self.assertTrue(photo['ref'].endswith('.png'))
        with urlopen(self.base+'/media/'+photo['ref']) as r:self.assertEqual(r.read(),binary)
        with self.assertRaisesRegex(ValueError,'32 MB'):
            media_bytes({'data':base64.b64encode(b'\x89PNG\r\n\x1a\n'+b'A'*32_000_000).decode()})

    def test_base_and_memory_through_api(self):
        with urlopen(self.base+'/api/bootstrap') as r:boot=json.load(r)
        self.assertEqual(len(boot['bases']),214)
        base=next(b for b in boot['bases'] if b['kind']=='structure' and b['params']=={'pole':'DT','structure':'N1'})
        query={'labor_id':'s1r4','base_id':base['id'],'base_mode':'instalado','context':'API teste'}
        def post(path,value):
            req=Request(self.base+path,data=json.dumps(value).encode(),headers={'X-App-Token':boot['token']},method='POST')
            with urlopen(req) as r:return json.load(r)
        editor=post('/api/base',query)['editor']
        removed=editor['materials'].pop(0)['material_id'];editor['reviewed']=True;editor['quantity']='2'
        result=post('/api/confirm-service',{'service':editor,'remember':True})
        self.assertEqual(result['service']['quantity'],'2')
        self.assertEqual(result['memory']['editor']['quantity'],'1')
        restored=post('/api/base',query)['editor']
        self.assertNotIn(removed,[r['material_id'] for r in restored['materials']])
        post('/api/confirm-service',{'service':dict(editor,variant='Somente esta obra'),'remember':False})
        with urlopen(self.base+'/api/backup') as r:backup=json.load(r)
        self.assertEqual(backup['schema'],4)
        self.assertTrue(backup['memories'])
        self.assertTrue(backup['memory_history'])
    def test_live_book_preview_is_read_only_and_handles_incomplete_draft(self):
        def post(value,token=app.TOKEN):
            request=Request(self.base+'/api/book-preview',data=json.dumps(value).encode(),headers={'X-App-Token':token},method='POST')
            with urlopen(request) as response:return json.load(response)
        before={table:app.records(table) for table in ('jobs','drafts','work_drafts')}
        with app.connect() as db:learning_before=app.learning.export_records(db)
        empty=post({'services':[],'book':{}})
        self.assertIn('Croqui não informado',empty['html'])
        self.assertIn('Nenhum ponto cadastrado',empty['html'])
        self.assertTrue(empty['pending'])
        self.assertNotIn('<script',empty['html'])
        raw={'work_order':'<img src=x onerror=alert(1)>','responsible':'Ana','book':{'points':[{'id':'p1','number':'1','installed':'Instalação confirmada','photos':[]}],'no_conductors':True},'services':[dict(service(),point_id='p1')]}
        preview=post(raw)
        self.assertIn('Instalação confirmada',preview['html'])
        self.assertIn('&lt;img src=x onerror=alert(1)&gt;',preview['html'])
        self.assertLess(preview['html'].index('CROQUI DA OBRA'),preview['html'].index('PONTO 1'))
        self.assertNotIn('Unitário (R$)',preview['html'])
        self.assertNotIn('MATERIAIS INSTALADOS',preview['html'])
        raw['book']['points'][0]['installed']='Mudança na observação'
        self.assertIn('Mudança na observação',' '.join(post(raw)['html'].split()))
        self.assertEqual(before,{table:app.records(table) for table in before})
        with app.connect() as db:learning_after=app.learning.export_records(db)
        self.assertEqual(learning_before['events'],learning_after['events'])
        self.assertEqual(learning_before['sources'],learning_after['sources'])
        with self.assertRaises(HTTPError) as error:post({},token='wrong')
        self.assertEqual(error.exception.code,403)

    def test_roundtrip_and_local_request_protection(self):
        with urlopen(self.base+'/api/bootstrap') as r: bootstrap=json.load(r)
        self.assertEqual(len(bootstrap['catalog']['materials']),2652)
        with urlopen(self.base+'/') as r:
            self.assertIn(b'Fechamento de obras',r.read());self.assertIn("frame-ancestors 'none'",r.headers['Content-Security-Policy'])
        for path in ['/app.js','/style.css']:
            with urlopen(self.base+path) as r:self.assertEqual(r.status,200);r.read()
        req=Request(self.base+'/api/calculate',data=json.dumps({'services':[service()]}).encode(),headers={'X-App-Token':bootstrap['token']},method='POST')
        with urlopen(req) as r:self.assertEqual(json.load(r)['materials'][0]['quantity'],'6')
        req=Request(self.base+'/api/calculate',data=b'{}',method='POST')
        with self.assertRaises(HTTPError) as e:urlopen(req)
        self.assertEqual(e.exception.code,403)
        req=Request(self.base+'/api/bootstrap',headers={'Host':'attacker.invalid'})
        with self.assertRaises(HTTPError) as e:urlopen(req)
        self.assertEqual(e.exception.code,403)

if __name__=='__main__':unittest.main()
