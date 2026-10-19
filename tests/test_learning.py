import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import app
import learning
from engine import LABOR,BASES,MATERIALS
from test_app import service


class LearningTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.old_dir,self.old_db=app.DATA_DIR,app.DB
        app.DATA_DIR=Path(self.temp.name);app.DB=app.DATA_DIR/'test.sqlite3'
    def tearDown(self):
        app.DATA_DIR,app.DB=self.old_dir,self.old_db;self.temp.cleanup()
    def payload(self,name='Ana',work='w1',coefficient='2',labor='s1r4',entry='entry1'):
        editor={**service(labor_id=labor,coefficient=coefficient),'entry_id':entry,'reviewed':False}
        return {'draft_id':work,'work_order':'OS-'+work,'responsible':name,'services':[],'editor':editor,'editor_touched':True,'editing':-1}
    def patterns(self):
        with app.connect() as db:return learning.patterns(db)
    def events(self):
        with app.connect() as db:return learning.read_rows(db,'learning_events')
    def test_automatic_save_does_not_require_review_or_save_button(self):
        data=self.payload();response=app.automatic_draft(data)
        self.assertEqual(response['learning']['changed'],1)
        self.assertEqual(len(self.events()),1);self.assertEqual(self.events()[0]['responsible'],'Ana')
        self.assertEqual(self.patterns()[0]['editor']['materials'][0]['coefficient'],'2')
        self.assertFalse(self.patterns()[0]['editor']['reviewed'])
        self.assertEqual(len(app.records('work_drafts')),1)
    def test_clear_current_draft_preserves_other_work_history_and_patterns(self):
        current=self.payload();other=self.payload('Bruno','w2')
        app.automatic_draft(current);app.automatic_draft(other)
        job=app.save_job({'work_order':'Salvo','services':[service()]})
        events=copy.deepcopy(self.events());patterns=copy.deepcopy(self.patterns())
        blank=app.clear_draft({'draft_id':current['draft_id'],'date':'2026-10-15'})['draft']
        self.assertNotEqual(blank['draft_id'],current['draft_id'])
        self.assertEqual(blank['services'],[]);self.assertIsNone(blank['book'])
        self.assertIsNone(blank['editor']);self.assertEqual(blank['work_order'],'')
        self.assertEqual(app.records('drafts'),[blank])
        self.assertEqual([d['draft_id'] for d in app.records('work_drafts')],['w2'])
        self.assertEqual(self.events(),events);self.assertEqual(self.patterns(),patterns)
        self.assertEqual(app.records('jobs')[0]['id'],job['id'])
        with self.assertRaisesRegex(ValueError,'rascunho foi limpo'):app.automatic_draft(current)
        self.assertEqual(app.records('drafts'),[blank])
        app.automatic_draft(blank)
        self.assertEqual([d['draft_id'] for d in app.records('work_drafts')],['w2'])

    def test_explicit_backup_restore_can_recover_a_cleared_draft(self):
        data=self.payload();app.automatic_draft(data);backup=app.backup_payload()
        app.clear_draft({'draft_id':data['draft_id']})
        self.assertIn(data['draft_id'],app.cleared_draft_ids())
        app.restore(backup)
        self.assertNotIn(data['draft_id'],app.cleared_draft_ids())
        self.assertEqual(app.records('drafts')[0]['work_order'],data['work_order'])
        app.automatic_draft(data)

    def test_partial_changes_stay_in_history_and_do_not_make_a_pattern(self):
        data=self.payload(coefficient='');app.automatic_draft(data)
        self.assertEqual(self.events()[0]['raw']['materials'][0]['coefficient'],'')
        self.assertEqual(self.patterns(),[])
        data['editor']['materials'][0]['coefficient']='3,5';app.automatic_draft(data)
        self.assertEqual(len(self.events()),2);self.assertEqual(self.patterns()[0]['uses'],1)
        self.assertEqual(self.patterns()[0]['editor']['materials'][0]['coefficient'],'3.5')
    def test_repeated_saves_count_and_editor_overrides_copy_in_same_snapshot(self):
        data=self.payload();data['services']=[copy.deepcopy(data['editor'])];data['editing']=0
        data['editor']['materials'][0]['coefficient']='4'
        for _ in range(6):app.automatic_draft(data)
        self.assertEqual(len(self.events()),6);self.assertEqual(self.patterns()[0]['uses'],6)
        self.assertEqual(self.patterns()[0]['editor']['materials'][0]['coefficient'],'4')
        data['editor']['materials'][0]['coefficient']='5';app.automatic_draft(data)
        self.assertEqual(len(self.events()),7);self.assertEqual(self.patterns()[0]['uses'],7)
        self.assertEqual(self.patterns()[0]['editor']['materials'][0]['coefficient'],'4')
    def test_patterns_count_every_responsible_and_detect_material_majority(self):
        first=self.payload('Ana','w1');second=self.payload('Bruno','w2');third=self.payload('Carla','w3')
        third['editor']['materials'].append({**third['editor']['materials'][0],'material_id':'m3','coefficient':'1'})
        for data in [first,second,third]:app.automatic_draft(data)
        result=self.patterns()[0]
        self.assertEqual((result['uses'],result['support'],result['responsibles']),(3,2,3))
        self.assertAlmostEqual(result['confidence'],66.7);self.assertTrue(result['auto_apply'])
        self.assertEqual(len(result['editor']['materials']),1)
        self.assertEqual({m['material_id']:m['occurrences'] for m in result['materials_frequency']},{'m2':3,'m3':1})
    def test_equal_material_sets_require_selection_and_personal_changes_survive(self):
        a=self.payload();b=self.payload('Bruno','w2');b['editor']['materials'].append({**b['editor']['materials'][0],'material_id':'m3'})
        app.automatic_draft(a);app.automatic_draft(b)
        with app.connect() as db:
            self.assertIsNone(learning.select(db,{'labor_id':'s1r4','responsible':'Novo'})['editor'])
            personal=learning.select(db,{'labor_id':'s1r4','responsible':'Bruno'})
        self.assertEqual(len(personal['editor']['materials']),2)
        self.assertFalse(self.patterns()[0]['auto_apply'])
    def test_install_remove_and_variants_never_mix(self):
        retirer=next(l['id'] for l in LABOR.values() if l['operation']=='RETIRAR')
        a=self.payload();b=self.payload('Ana','w2',labor=retirer);b['editor']['materials'][0]['movement']='desativado'
        c=self.payload('Ana','w3');c['editor']['variant']='Outra configuração'
        for data in [a,b,c]:app.automatic_draft(data)
        results=self.patterns();self.assertEqual(len(results),3)
        self.assertTrue(all(p['uses']==1 for p in results))
        removed=next(p for p in results if p['editor']['operation']=='RETIRAR')
        self.assertEqual(removed['editor']['materials'][0]['movement'],'desativado')
    def test_transformer_needs_context_but_raw_change_is_saved(self):
        data=self.payload();base=next(b for b in BASES.values() if b['kind']=='transformer')
        data['editor'].update(base_id=base['id'],base_mode='planilha',context='')
        app.automatic_draft(data);self.assertEqual(self.patterns(),[]);self.assertEqual(len(self.events()),1)
        data['editor']['context']='75 kVA';app.automatic_draft(data)
        self.assertEqual(len(self.patterns()),1)
    def test_missing_responsible_saved_then_identified(self):
        data=self.payload(name='');app.automatic_draft(data);self.assertEqual(self.patterns(),[])
        self.assertEqual(len(self.events()),1)
        data['responsible']='Ana';app.automatic_draft(data);self.assertEqual(self.patterns()[0]['uses'],1)
    def test_deleted_material_and_deleted_service_are_respected(self):
        data=self.payload();data['editor']['materials'].append({**data['editor']['materials'][0],'material_id':'m3'})
        app.automatic_draft(data);data['editor']['materials'].pop();app.automatic_draft(data)
        self.assertEqual(len(self.patterns()[0]['editor']['materials']),1)
        data['services']=[data.pop('editor')];data['editor_touched']=False;app.automatic_draft(data)
        data['services']=[];app.automatic_draft(data);self.assertEqual(self.patterns()[0]['uses'],3)
        self.assertTrue(self.events()[-1]['inactive'])
        with app.connect() as db:
            self.assertTrue(all(not s['editor'] for s in learning.read_rows(db,'learning_sources')))
    def test_duplicates_with_same_entry_id_in_list_are_preserved(self):
        data=self.payload();data['services']=[copy.deepcopy(data['editor']),copy.deepcopy(data['editor'])];data['editor']=None
        app.automatic_draft(data)
        self.assertEqual(self.patterns()[0]['uses'],2)
        self.assertEqual(len({e['id'] for e in self.events()}),2)
    def test_transport_retry_same_record_id_is_not_a_new_save(self):
        data=self.payload();data['record_id']='request-1'
        app.automatic_draft(data);app.automatic_draft(data)
        self.assertEqual(len(self.events()),1)
        data['record_id']='request-2';app.automatic_draft(data)
        self.assertEqual(len(self.events()),2)
    def test_explicit_job_saves_include_identical_compositions_and_backfill_is_stable(self):
        data=self.payload();data['services']=[data.pop('editor')]
        for _ in range(3):app.save_job(data)
        self.assertEqual(self.patterns()[0]['uses'],3)
        app.learning_bootstrap();app.learning_bootstrap()
        self.assertEqual(self.patterns()[0]['uses'],3)
    def test_unknown_labor_is_preserved_as_incomplete_raw_record(self):
        data=self.payload();data['editor']['labor_id']='new_unknown_labor'
        app.automatic_draft(data)
        self.assertEqual(len(self.events()),1);self.assertEqual(self.patterns(),[])
    def test_sync_export_contains_responsible_but_no_book_or_work_notes(self):
        data=self.payload();data['editor']['note']='NOTA PRIVADA';data['editor']['point_id']='PONTO-PRIVADO'
        app.automatic_draft(data)
        with app.connect() as db:events=learning.sync_events(db)
        text=json.dumps(events)
        self.assertIn('Ana',text)
        for field in ['NOTA PRIVADA','PONTO-PRIVADO','OS-w1','work_order','work_id']:self.assertNotIn(field,text)
    def test_periodic_named_export_and_cross_computer_import_are_idempotent(self):
        a=self.payload(name='Ana / Silva');app.automatic_draft(a)
        files=list((app.DATA_DIR/'registros_responsaveis').glob('*.json'));self.assertEqual(len(files),1)
        exported=json.loads(files[0].read_text());self.assertEqual(exported['responsible'],'Ana / Silva')
        self.assertTrue((app.DATA_DIR/'padroes_aprendidos.json').exists())
        with app.connect() as db:bundle=learning.export_records(db)
        app.DB=app.DATA_DIR/'other.sqlite3'
        app.automatic_draft(self.payload('Bruno','w2'))
        with app.connect() as db:
            self.assertEqual(learning.import_records(db,bundle)['imported'],1)
            self.assertEqual(learning.import_records(db,bundle)['imported'],0)
        self.assertEqual(self.patterns()[0]['uses'],2)
    def test_published_base_works_on_new_install_and_contains_no_names_or_jobs(self):
        app.automatic_draft(self.payload('Pessoa de Teste','obra_secreta'))
        with app.connect() as db:bundle=learning.export_patterns(db)
        text=json.dumps(bundle)
        self.assertNotIn('Pessoa de Teste',text);self.assertNotIn('obra_secreta',text)
        app.DB=app.DATA_DIR/'new.sqlite3'
        with patch('learning.bundled_samples',return_value=learning.validate_samples(bundle['samples'])):
            self.assertEqual(self.patterns()[0]['uses'],1)
            with app.connect() as db:learning.import_records(db,bundle)
            self.assertEqual(self.patterns()[0]['uses'],1)
        backup=app.backup_payload();app.DB=app.DATA_DIR/'restore.sqlite3';app.restore(backup)
        self.assertEqual(self.patterns()[0]['uses'],1)
    def test_backup_restores_raw_history_and_all_work_drafts(self):
        app.automatic_draft(self.payload());app.automatic_draft(self.payload('Bruno','w2',coefficient=''))
        backup=app.backup_payload();app.DB=app.DATA_DIR/'restored.sqlite3';app.restore(backup)
        self.assertEqual(len(self.events()),2);self.assertEqual(len(app.records('work_drafts')),2)
        self.assertEqual(len(self.patterns()),1)
    def test_representative_quantities_are_an_actual_record(self):
        a=self.payload();b=self.payload('Bruno','w2','3')
        a['editor']['materials'].append({**a['editor']['materials'][0],'material_id':'m3','coefficient':'10'})
        b['editor']['materials'].append({**b['editor']['materials'][0],'material_id':'m3','coefficient':'20'})
        app.automatic_draft(a);app.automatic_draft(b)
        pattern=self.patterns()[0]
        quantities=[r['coefficient'] for r in pattern['editor']['materials']]
        self.assertIn(quantities,[['2','10'],['3','20']]);self.assertEqual(pattern['quantity_variations'],2)
    def test_future_catalog_reordering_uses_codes_not_stale_row_ids(self):
        app.automatic_draft(self.payload());original=copy.deepcopy(MATERIALS['m2'])
        reordered={**original,'id':'new_material_id'}
        replacement={**original,'code':'OTHER-CODE','description':'Outro material'}
        with patch.dict(MATERIALS,{'m2':replacement,'new_material_id':reordered}):
            pattern=self.patterns()[0]
            self.assertEqual(pattern['editor']['materials'][0]['material_id'],'new_material_id')
            self.assertEqual(pattern['editor']['materials'][0]['code'],original['code'])


if __name__=='__main__':unittest.main()
