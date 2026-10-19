import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import app
import engine
import compositions as comp

def find_base(kind,**params):
    return next(b for b in engine.BASES.values() if b['kind']==kind and all(b['params'].get(k)==v for k,v in params.items()))

def selection(structure='N1',labor='s1r4',mode='instalado',context=''):
    return {'labor_id':labor,'base_id':find_base('structure',pole='DT',structure=structure)['id'],'base_mode':mode,'context':context}

def ready_editor(**kwargs):
    e=comp.base_editor(selection(**kwargs))['editor'];e['reviewed']=True
    for r in e['materials']:
        if not r['unit']:r['unit']='PC'
    return e

class BaseTests(unittest.TestCase):
    def test_counts_and_structure_quantities(self):
        bases=list(engine.BASES.values())
        self.assertEqual(sum(b['kind']=='structure' for b in bases),102)
        self.assertEqual(sum(b['kind']=='transformer' for b in bases),112)
        self.assertEqual(sum(len(b['rows']) for b in bases),2911)
        n1=comp.base_editor(selection())['editor']
        self.assertEqual([r['coefficient'] for r in n1['materials']],['1','3','2','2','5','2','3'])
        self.assertEqual([r['code'] for r in n1['materials']],['90404','90251','90444','90360','90389','90364','90253'])
        self.assertTrue(all(r['movement']=='instalado' for r in n1['materials']))
        removed=comp.base_editor(selection(mode='desativado',labor='s1r6'))['editor']
        self.assertTrue(all(r['movement']=='desativado' for r in removed['materials']))

    def test_transformer_keeps_two_independent_columns(self):
        b=find_base('transformer',phase='3F',voltage='13.8KV',power='ACIMA DE 75 KVA',fuse_position='NO TRAFO',bt_type='ISOLADA',bt_exit='DUPLA')
        args={'labor_id':'s1r4','base_id':b['id'],'base_mode':'planilha','context':'112,5 kVA'}
        rows=comp.base_editor(args)['editor']['materials']
        values={(r['code'],r['movement']):r['coefficient'] for r in rows}
        self.assertEqual(values['90257','instalado'],'0.5')
        self.assertEqual(values['90290','instalado'],'4')
        self.assertEqual(values['90207','instalado'],'3')
        self.assertEqual(values['90207','desativado'],'3')
        self.assertNotIn(('90257','desativado'),values)
        removed=comp.base_editor(dict(args,base_mode='desativado'))['editor']['materials']
        self.assertTrue(all(r['movement']=='desativado' for r in removed))
        self.assertEqual(len(removed),3)
        self.assertEqual(len(rows),18)

    def test_missing_unit_not_invented_and_crossarm_mismatch_visible(self):
        result=comp.base_editor(selection(structure='B1'))
        row=next(r for r in result['editor']['materials'] if r['code']=='90442')
        self.assertEqual(row['unit'],'')
        self.assertTrue(any('PRFV' in w for w in result['warnings']))
        self.assertTrue(any('90442' in w for w in result['warnings']))

class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.prev_dir,self.prev_db=app.DATA_DIR,app.DB
        app.DATA_DIR=Path(self.tmp.name);app.DB=app.DATA_DIR/'fechamento.sqlite3'
    def tearDown(self):
        app.DATA_DIR,app.DB=self.prev_dir,self.prev_db;self.tmp.cleanup()

    def test_add_remove_edit_then_restart(self):
        editor=ready_editor();removed=editor['materials'].pop(0)
        editor['materials'][0]['coefficient']='8'
        editor['materials'].append({'material_id':'m2','unit':'PC','coefficient':'2','movement':'instalado'})
        editor['quantity']='5'
        memory=app.remember(editor)
        self.assertEqual(memory['editor']['quantity'],'1')
        self.assertEqual(len(memory['difference']['removed']),1)
        self.assertEqual(len(memory['difference']['added']),1)
        self.assertEqual(len(memory['difference']['changed']),1)
        loaded=app.load_base(selection())
        self.assertEqual(loaded['memory']['id'],memory['id'])
        self.assertNotIn(removed['code'],[r['code'] for r in loaded['editor']['materials']])
        self.assertFalse(loaded['editor']['reviewed'])
        env={**os.environ,'ENGELMIG_DATA_DIR':self.tmp.name}
        code='import app,json; print(json.dumps(app.load_base('+repr(selection())+')["editor"]))'
        output=subprocess.check_output([sys.executable,'-c',code],cwd=engine.ROOT,env=env,text=True)
        reopened=json.loads(output)
        self.assertEqual(reopened['materials'],loaded['editor']['materials'])
        original=app.load_base({**selection(),'original':True})
        self.assertIn(removed['code'],[r['code'] for r in original['editor']['materials']])
        self.assertIsNone(original['memory'])

    def test_variant_operation_context_and_movement_isolation(self):
        app.remember(ready_editor())
        for query in [selection(structure='N2'),selection(labor='s1r6'),selection(mode='desativado'),selection(context='Especial')]:
            self.assertIsNone(app.load_base(query)['memory'])
        self.assertIsNotNone(app.load_base(selection())['memory'])

    def test_revision_recovery_and_forget(self):
        editor=ready_editor();one=app.remember(editor)
        self.assertEqual(one['revision'],1)
        self.assertEqual(app.remember(editor)['revision'],1)
        self.assertEqual(len(app.records('memory_history')),1)
        first_event=app.records('memory_history')[0]
        editor['materials'][0]['coefficient']='4'
        two=app.remember(editor);self.assertEqual(two['revision'],2)
        recovered=app.recover_memory(first_event['id'])
        self.assertEqual(recovered['editor']['materials'][0]['coefficient'],'1')
        self.assertEqual(recovered['revision'],3)
        app.forget_memory(one['id'])
        self.assertIsNone(app.load_base(selection())['memory'])
        self.assertTrue(app.records('memory_history'))

    def test_closed_job_snapshot_does_not_change(self):
        e=ready_editor();job=app.save_job({'work_order':'V2 TESTE','status':'fechado','services':[e]})
        saved=copy.deepcopy(job['result'])
        e['materials'][0]['coefficient']='10';app.remember(e)
        self.assertEqual(app.records('jobs')[0]['result'],saved)

    def test_no_learning_until_reviewed_and_no_partial_write(self):
        e=ready_editor();e['reviewed']=False
        with self.assertRaises(ValueError):app.remember(e)
        self.assertEqual(app.records('memories'),[])
        e['reviewed']=True;e['materials'][0]['coefficient']=''
        with self.assertRaises(ValueError):app.remember(e)
        self.assertEqual(app.records('memory_history'),[])

    def test_transformer_requires_specific_variant_for_memory(self):
        b=find_base('transformer',phase='1F',voltage='13.8KV',power='ATÉ 30 KVA',fuse_position='NO TRAFO',bt_type='ISOLADA',bt_exit='NORMAL')
        e=comp.base_editor({'labor_id':'s1r4','base_id':b['id'],'base_mode':'planilha'})['editor'];e['reviewed']=True
        with self.assertRaises(ValueError):app.remember(e)
        e['context']='25 kVA';memory=app.remember(e)
        self.assertIsNotNone(memory)
        self.assertIsNone(app.load_base({**e,'context':'15 kVA'})['memory'])

    def test_backup_v2_includes_memory_and_history(self):
        memory=app.remember(ready_editor())
        backup={'app':app.APP_ID,'schema':2,'profiles':[],'jobs':[],'memories':app.records('memories'),'memory_history':app.records('memory_history')}
        app.forget_memory(memory['id'])
        result=app.restore(backup)
        self.assertEqual(result['memories'],1)
        self.assertIsNotNone(app.load_base(selection())['memory'])
        bad=copy.deepcopy(backup);bad['memories'][0]['id']='wrong'
        with self.assertRaises(ValueError):app.restore(bad)
        self.assertEqual(len(app.records('memories')),1)

if __name__=='__main__':unittest.main()
