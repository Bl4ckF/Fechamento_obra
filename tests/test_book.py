import base64
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
import app
import book
import geo
from book_report import book_html, materials_report_html, labor_totals, wrap_text, table_groups
from test_app import service

PNG='iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j9oUAAAAASUVORK5CYII='

def point(ident,label,ref):
    return {'id':ident,'number':label,'coordinate':'-20.47, -54.62','photos':[{'ref':ref,'stage':'Depois','caption':'Conferência visual'}]}

class BookTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.old_dir,self.old_db=app.DATA_DIR,app.DB
        app.DATA_DIR=Path(self.temp.name);app.DB=app.DATA_DIR/'fechamento.sqlite3'
        self.ref=book.put_media({'data':PNG,'name':'teste.png'},app.DATA_DIR/'media')['ref']
        self.book={'points':[point('p1','1',self.ref),point('p2','2',self.ref)],'croqui':{'ref':self.ref},'no_conductors':False,'conductors':[{'id':'t1','from_point':'p1','to_point':'p2','code':'C1','description':'Cabo A','gauge':'50 mm²','movement':'instalado','length':'35,5','count':3,'extra':'2,5'},{'id':'t2','from_point':'p1','to_point':'p2','code':'C1','description':'Cabo A','gauge':'50 mm²','movement':'desativado','length':'20','count':3,'extra':'0'}]}
        self.services=[dict(service(),point_id='p1'),dict(service('s1r6',quantity='1',coefficient='1',movement='desativado'),point_id='p2')]
    def tearDown(self):
        app.DATA_DIR,app.DB=self.old_dir,self.old_db
        self.temp.cleanup()

    def test_conductor_sum_and_movement_are_independent(self):
        result=book.normalize_book(self.book,self.services,app.available_media())
        self.assertEqual([r['total'] for r in result['conductors']],['109','60'])
        self.assertEqual({r['movement']:r['total'] for r in result['conductor_totals']},{'instalado':'109','desativado':'60'})
        self.assertTrue(result['ready'])

    def test_materials_link_to_point_without_duplication(self):
        result=book.normalize_book(self.book,self.services,app.available_media())
        self.assertEqual(result['points'][0]['materials'][0]['quantity'],'6')
        self.assertEqual(result['points'][1]['materials'][0]['quantity'],'1')
        self.assertEqual(result['points'][0]['materials'][0]['movement'],'instalado')
        self.assertEqual(result['points'][1]['materials'][0]['movement'],'desativado')

    def test_completion_blocks_missing_photos_croqui_and_assignment(self):
        bad=copy.deepcopy(self.book);bad['points'][0]['photos']=[];bad['croqui']=None
        payload={'work_order':'QA','services':[service()],'book':bad,'status':'fechado'}
        with self.assertRaises(ValueError):app.save_job(payload)
        payload['status']='rascunho';saved=app.save_job(payload)
        self.assertFalse(saved['book']['ready']);self.assertGreaterEqual(len(saved['book']['pending']),3)

    def test_forms_is_a_separate_manual_stage(self):
        payload={'work_order':'QA','services':self.services,'book':self.book,'status':'fechado'}
        first=app.save_job(payload);self.assertEqual(first['workflow'],'aguardando_forms')
        payload['book']['forms_submitted']=True
        second=app.save_job(payload);self.assertEqual(second['workflow'],'concluido')
        self.assertFalse(next(j for j in app.records('jobs') if j['id']==first['id'])['book']['forms_submitted'])

    def test_forms_login_url_is_converted_without_session_parameters(self):
        from urllib.parse import urlencode
        state=base64.urlsafe_b64encode(json.dumps({'data':{'.redirect':book.DEFAULT_FORMS_URL+'&sid=session-only'}}).encode()).decode().rstrip('=')
        url='https://login.microsoftonline.com/organizations/oauth2/v2.0/authorize?'+urlencode({'state':state,'nonce':'private-nonce','login_hint':'someone@example.com'})
        self.assertEqual(book.clean_settings({'forms_url':url})['forms_url'],book.DEFAULT_FORMS_URL)
        self.assertEqual(book.clean_settings({'forms_url':book.LEGACY_FORMS_URL})['forms_url'],book.DEFAULT_FORMS_URL)
        with self.assertRaises(ValueError):book.clean_settings({'forms_url':'https://login.microsoftonline.com/authorize?state=invalid'})

    def test_records_branch_must_be_separate_from_program(self):
        config=book.clean_settings({});self.assertTrue(config['sync_enabled'])
        self.assertEqual(config['sync_branch'],'registros-materiais')
        for branch in ('main','../main','a//b','x.lock'):
            with self.assertRaises(ValueError):book.clean_settings({'sync_branch':branch})

    def test_backup_contains_media_and_restores_after_loss(self):
        job=app.save_job({'work_order':'QA','services':self.services,'book':self.book,'status':'fechado'})
        backup=app.backup_payload();self.assertEqual(backup['schema'],4);self.assertEqual(len(backup['media']),1)
        (app.DATA_DIR/'media'/self.ref).unlink()
        with app.connect() as db:db.execute('DELETE FROM jobs')
        result=app.restore(backup)
        self.assertEqual(result['media'],1);self.assertTrue((app.DATA_DIR/'media'/self.ref).exists())
        self.assertEqual(app.records('jobs')[0]['id'],job['id'])
        bad=copy.deepcopy(backup);bad['media'][0]['ref']='a'*64+'.png'
        with self.assertRaises(ValueError):app.restore(bad)

    def test_invalid_references_and_conflicting_conductor_declaration(self):
        for change in [lambda b:b['points'][1].update(number='1'),lambda b:b['conductors'][0].update(from_point='missing'),lambda b:b['conductors'][0].update(count='2.5'),lambda b:b['conductors'][0].update(length='NaN'),lambda b:b.update(no_conductors=True)]:
            bad=copy.deepcopy(self.book);change(bad)
            with self.assertRaises(ValueError):book.normalize_book(bad,self.services,app.available_media())
        bad=copy.deepcopy(self.book);bad['points'][0]['photos'][0]['ref']='../app.py'
        with self.assertRaises(ValueError):book.normalize_book(bad,self.services,app.available_media())

    def test_report_has_photo_model_croqui_conductors_and_escaped_input(self):
        payload={'work_order':'<script>alert(1)</script>','services':self.services,'book':self.book,'status':'fechado'}
        report=book_html(app.save_job(payload)).decode()
        self.assertIn('BOOK FOTOGRÁFICO',report);self.assertIn('OBSERVAÇÕES',report)
        self.assertIn('CROQUI DA OBRA',report);self.assertIn('SOMAGEM DOS CONDUTORES',report)
        self.assertNotIn('<script>alert(1)</script>',report);self.assertIn('&lt;script&gt;',report)
        self.assertIn('109',report);self.assertIn('60',report)

    def test_croqui_first_and_only_install_remove_labor_in_book(self):
        from engine import LABOR
        execute=next(s for s in LABOR.values() if s['operation']=='EXECUTAR')
        other={'labor_id':execute['id'],'quantity':'1','materials':[],'no_materials':True,'reviewed':True,'point_id':'p1'}
        job=app.save_job({'work_order':'QA','services':self.services+[other],'book':self.book})
        report=book_html(job).decode()
        first_page=report.split('<article',1)[1].split('</article>',1)[0]
        self.assertIn('CROQUI DA OBRA',first_page)
        self.assertNotIn('MÃO DE OBRA POR PONTO',report);self.assertNotIn('DETALHAMENTO POR PONTO',report);self.assertIn('INSTALADO',report)
        for s in job['result']['services'][:2]:self.assertIn(s['description'],' '.join(report.split()))
        self.assertNotIn(execute['description'],report)
        self.assertNotIn('Materiais</h2>',report)
        for m in job['result']['materials']:self.assertNotIn(m['description'],report)
        separate=materials_report_html(job).decode()
        self.assertIn(execute['description'],separate)
        for m in job['result']['materials']:self.assertIn(m['description'],separate)
        self.assertNotIn('Composição do serviço',separate)

    def test_report_totals_merge_repeated_labor_and_preserve_operations(self):
        from decimal import Decimal
        services=[dict(service(quantity='0.1'),point_id='p1'),
                  dict(service(quantity='0.2'),point_id='p2'),self.services[1]]
        job=app.save_job({'work_order':'QA','services':services,'book':self.book})
        totals=labor_totals(job['result']['services'])
        self.assertEqual(len(totals),2)
        self.assertEqual({s['operation']:s['quantity'] for s in totals},
                         {'INSTALAR':Decimal('0.3'),'RETIRAR':Decimal('1')})
        self.assertEqual({m['movement']:m['quantity'] for m in job['result']['materials']},
                         {'instalado':'0.6','desativado':'1'})
        report=materials_report_html(job).decode()
        self.assertIn('Total de mãos de obra',report)
        self.assertIn('0,3',report)
        self.assertNotIn('Composição do serviço',report)
        self.assertNotIn('Qtd./serviço',report)
        self.assertEqual(report.count('<article'),3)

    def test_book_uses_selected_structure_and_utm_without_network_ids(self):
        from engine import BASES,LABOR
        base=next(b for b in BASES.values() if b['kind']=='structure' and b['params']=={'pole':'DT','structure':'N1'})
        removed=next(b for b in BASES.values() if b['kind']=='structure' and b['params']=={'pole':'DT','structure':'N2'})
        services=[dict(self.services[0],base_id=base['id'],variant='DT · N1'),dict(self.services[1],base_id=removed['id'],variant='DT · N2')]
        raw=copy.deepcopy(self.book)
        raw['points'][0].update(td='TD-SECRET-111',rd='RD-SECRET-222',circuit='CKT-SECRET-333',network_source='proximidade')
        job=app.save_job({'work_order':'QA','services':services,'book':raw})
        report=book_html(job).decode()
        for text in ['TD-SECRET-111','RD-SECRET-222','CKT-SECRET-333','Religador:','Circuito:','TD:',LABOR[services[0]['labor_id']]['description']]:self.assertNotIn(text,report)
        self.assertIn('Estrutura N1 · poste DT',' '.join(report.split()));self.assertIn('Estrutura N2 · poste DT',' '.join(report.split()))
        self.assertIn(geo.format_utm(-20.47,-54.62),report)
        self.assertEqual(job['book']['points'][0]['td'],'TD-SECRET-111')
        self.assertEqual(job['book']['points'][0]['coordinate'],geo.format_utm(-20.47,-54.62))
        self.assertIn(LABOR[services[0]['labor_id']]['description'],materials_report_html(job).decode())
        # Um registro já salvo em graus também sai em UTM ao gerar o PDF.
        job['book']['points'][0]['coordinate']='-20.47, -54.62'
        self.assertIn(geo.format_utm(-20.47,-54.62),book_html(job).decode())
        self.assertNotIn('-20.47, -54.62',book_html(job).decode())

    def test_symbols_survive_job_backup_and_restore(self):
        raw=copy.deepcopy(self.book)
        raw['drawing']={'version':1,'background_ref':self.ref,'objects':[{'id':'sym_1','type':'symbol','symbol_id':'religador','x1':200,'y1':250,'size':75,'rotation':45,'label':'P1','status':'instalar'}]}
        saved=app.save_job({'work_order':'Símbolos','services':self.services,'book':raw})
        backup=app.backup_payload()
        with app.connect() as db:db.execute('DELETE FROM jobs')
        app.restore(backup)
        restored=next(j for j in app.records('jobs') if j['id']==saved['id'])
        self.assertEqual(restored['book']['drawing'],saved['book']['drawing'])

    def test_separate_csv_preserves_material_service_link_and_duplicates(self):
        import csv,io
        job=app.save_job({'work_order':'QA','services':self.services+[self.services[0]],'book':self.book})
        rows=list(csv.reader(io.StringIO(app.report_csv(job).decode('utf-8-sig')),delimiter=';'))
        start=next(i for i,row in enumerate(rows) if row==['MATERIAIS POR MÃO DE OBRA'])
        detail=rows[start+2:]
        self.assertEqual([row[0] for row in detail],['1','2','3'])
        self.assertEqual(detail[0][1],'1')
        self.assertEqual(detail[0][-1],'6')
        self.assertEqual(detail[2][-1],'6')

    def test_point_does_not_leak_into_memory(self):
        s=dict(service(),point_id='p1')
        memory=app.remember(s)
        self.assertEqual(memory['editor']['point_id'],'')
        self.assertEqual(app.calculate([s])['services'][0]['point_id'],'p1')

    def test_long_report_text_continues_without_losing_words(self):
        words=('Texto de conferência '+('X'*300)+'\n')*40
        pages=wrap_text(words,1800)
        self.assertGreater(len(pages),1)
        self.assertEqual(''.join(''.join(pages).split()),''.join(words.split()))
        self.assertTrue(all(len(p.splitlines())<=32 for p in pages))
        rows=[{'description':'Condutor '+('alumínio '*60)} for _ in range(20)]
        groups=table_groups(rows,lambda r:[r['description']],[29],175)
        self.assertGreater(len(groups),1)
        self.assertEqual(sum(groups,[]),rows)

class GeoTests(unittest.TestCase):
    def test_decimal_directional_and_dms(self):
        for s in ['-20.554185, -54.578959','-20,554185 -54,578959','20.554185°S 54.578959°W',"20°33'15.066\"S 54°34'44.2524\"W"]:
            lat,lon=geo.parse_coord(s);self.assertAlmostEqual(lat,-20.554185,places=6);self.assertAlmostEqual(lon,-54.578959,places=6)
        for s in ['91, 200','TD-123','21K 12 34','abc','20°99\'10"S 54°10\'1"W']:
            with self.assertRaises(ValueError):geo.parse_coord(s)

    def test_utm_equator_and_southern_reference(self):
        lat,lon=geo.parse_coord('31N 500000 0000000');self.assertAlmostEqual(lat,0,places=6);self.assertAlmostEqual(lon,3,places=6)
        lat,lon=geo.parse_coord('21K 753302 7725693');self.assertTrue(-21<lat<-20);self.assertTrue(-55<lon<-54)

    def test_utm_format_projection_reference_values_and_roundtrip(self):
        # PROJ examples use neighboring zones at the boundaries; symmetric E.
        z,b,e,n=geo.latlon_to_utm(-44,174)
        self.assertEqual((z,b),(60,'G'))
        self.assertAlmostEqual(e,1000000-740526.32,places=2)
        self.assertAlmostEqual(n,5123750.87,places=2)
        z,b,e,n=geo.latlon_to_utm(56,12)
        self.assertEqual((z,b),(33,'V'))
        self.assertAlmostEqual(e,1000000-687071.44,places=2)
        self.assertAlmostEqual(n,6210141.33,places=2)
        for lat,lon in [(-20.554185,-54.578959),(-20.47,-54.62),(0,3),(-16,-56),(-24,-53),(60,6),(75,15),(83.5,25)]:
            value=geo.format_utm(lat,lon);y,x=geo.parse_coord(value)
            self.assertLess(geo.distance(lat,lon,y,x),1)
        self.assertTrue(geo.format_utm(-20.47,-54.62).startswith('21K '))
        self.assertTrue(geo.format_utm(-20,-51).startswith('22K '))
        with self.assertRaises(ValueError):geo.latlon_to_utm(85,0)

    def test_actual_equipment_exact_location_and_radius(self):
        kind,code,lat,lon,circuit=geo.equipment()[0]
        hit=geo.search(code)['results'][0];self.assertEqual(hit['circuit'],circuit)
        near=geo.nearest(lat,lon,50)['td'][0];self.assertEqual(near['distance_m'],0);self.assertEqual(near['code'],code)
        self.assertEqual(geo.nearest(0,0,50),{'td':[],'rd':[]})
        self.assertEqual(len(geo.equipment()),25940)

if __name__=='__main__':unittest.main()
