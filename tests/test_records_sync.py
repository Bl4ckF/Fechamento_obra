import copy
import json
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import learning
from records_sync import RecordSync
from test_app import service


class RepositorySyncTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.remote=self.root/'shared.git'
        subprocess.run(['git','init','--bare',str(self.remote)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        self.a=self.machine('a');self.b=self.machine('b')
        blob=self.a.git(self.remote,'hash-object','-w','--stdin',content=b'programa original').stdout.strip()
        tree=self.a.git(self.remote,'mktree',content=b'100644 blob '+blob+b'\tapp.py\n').stdout.decode().strip()
        self.main=self.a.git(self.remote,'commit-tree',tree,content=b'Programa\n').stdout.decode().strip()
        self.a.git(self.remote,'update-ref','refs/heads/main',self.main)

    def tearDown(self):self.temp.cleanup()

    def database(self,name):
        db=sqlite3.connect(self.root/(name+'.sqlite3'));learning.ensure(db);return db

    def machine(self,name):
        config={'repository':str(self.remote),'branch':'main','sync_branch':'registros-materiais','sync_enabled':True}
        def export():
            with self.database(name) as db:return learning.sync_events(db)
        def merge(events):
            with self.database(name) as db:return learning.import_records(db,{'schema':1,'kind':'registros_ajustes','events':events})
        return RecordSync(self.root/name,lambda:config,export,merge)

    def save(self,name,amount='2',times=1):
        raw={**service(coefficient=amount),'entry_id':'entry','note':'nota privada'}
        with self.database(name) as db:
            for _ in range(times):learning.capture(db,{'draft_id':name,'work_order':'OS PRIVADA','responsible':name.upper(),'services':[raw]})

    def count(self,name):
        with self.database(name) as db:return learning.patterns(db)[0]['uses']

    def remote_count(self):
        result=self.a.git(self.remote,'ls-tree','-r','--name-only','refs/heads/registros-materiais').stdout.decode()
        return len([p for p in result.splitlines() if p.endswith('.json')])

    def test_two_machines_repeated_records_and_downloads(self):
        self.save('a',times=3);self.save('b',times=2)
        self.assertEqual(self.a.sync_once()['uploaded'],3)
        state=self.b.sync_once();self.assertFalse(state['error']);self.assertEqual(state['downloaded'],3)
        self.a.sync_once()
        self.assertEqual(self.count('a'),5);self.assertEqual(self.count('b'),5)
        self.a.sync_once();self.b.sync_once();self.assertEqual(self.remote_count(),5);self.assertEqual(self.count('a'),5)
        self.assertEqual(self.a.git(self.remote,'rev-parse','refs/heads/main').stdout.decode().strip(),self.main)
        tip=self.a.git(self.remote,'rev-parse','refs/heads/registros-materiais').stdout.decode().strip()
        tree=self.a.git(self.remote,'ls-tree','-r','--name-only',tip).stdout.decode()
        self.assertNotIn('app.py',tree)

    def test_simultaneous_initial_pushes_rebase_union_without_overwrite(self):
        self.save('a');self.save('b',amount='4')
        original=self.a.git;intervened=False
        def interleaved(cache,*args,**kwargs):
            nonlocal intervened
            if args[0]=='push' and not intervened:
                intervened=True;self.assertFalse(self.b.sync_once()['error'])
            return original(cache,*args,**kwargs)
        with patch.object(self.a,'git',side_effect=interleaved):state=self.a.sync_once()
        self.assertFalse(state['error'],state['error']);self.assertTrue(intervened)
        self.assertEqual(self.remote_count(),2);self.assertEqual(self.count('a'),2)
        self.b.sync_once();self.assertEqual(self.count('b'),2)

    def test_simultaneous_updates_preserve_both_branches_of_new_records(self):
        self.save('a');self.a.sync_once();self.b.sync_once()
        self.save('a',times=2);self.save('b')
        original=self.a.git;once=False
        def interleaved(cache,*args,**kwargs):
            nonlocal once
            if args[0]=='push' and not once:once=True;self.b.sync_once()
            return original(cache,*args,**kwargs)
        with patch.object(self.a,'git',side_effect=interleaved):state=self.a.sync_once()
        self.assertFalse(state['error'],state['error']);self.assertEqual(self.remote_count(),4)

    def test_write_denied_keeps_local_events_and_retries(self):
        self.save('a',times=2);original=self.a.git
        def denied(cache,*args,**kwargs):
            if args[0]=='push':return subprocess.CompletedProcess(args,128,b'',b'Permission denied')
            return original(cache,*args,**kwargs)
        with patch.object(self.a,'git',side_effect=denied):state=self.a.sync_once()
        self.assertIn('permissão',state['error']);self.assertEqual(state['pending'],2);self.assertEqual(self.count('a'),2)
        state=self.a.sync_once();self.assertFalse(state['error']);self.assertEqual(state['pending'],0);self.assertEqual(self.remote_count(),2)

    def test_offline_read_failure_does_not_create_a_replacement_history(self):
        self.save('a');self.a.sync_once();self.save('a')
        original=self.a.git
        def offline(cache,*args,**kwargs):
            if args[0]=='ls-remote':return subprocess.CompletedProcess(args,128,b'',b'Network unreachable')
            return original(cache,*args,**kwargs)
        with patch.object(self.a,'git',side_effect=offline):self.assertTrue(self.a.sync_once()['error'])
        self.assertEqual(self.remote_count(),1);self.assertEqual(self.count('a'),2)
        self.assertFalse(self.a.sync_once()['error']);self.assertEqual(self.remote_count(),2)

    def test_disabled_and_code_branch_not_used(self):
        config=self.a.settings();config['sync_enabled']=False
        with patch.object(self.a,'git',side_effect=AssertionError('No Git for disabled sync')):self.a.sync_once()
        config.update(sync_enabled=True,sync_branch='main')
        self.assertIn('branch exclusiva',self.a.sync_once()['error'])

    def test_error_from_previous_repository_is_not_shown_after_link_change(self):
        config=self.a.settings()
        self.a.state.update(configuration=[config['repository'],config['sync_branch']],error='Falha antiga',last_success='2026-01-01')
        self.assertEqual(self.a.status()['error'],'Falha antiga')
        config['repository']='https://github.com/another/project'
        self.assertEqual(self.a.status()['error'],'');self.assertIsNone(self.a.status()['last_success'])

    def test_git_access_error_identifies_account_requirement(self):
        message=RecordSync.connection_error("remote: Repository not found. fatal: repository not found")
        self.assertIn('conta',message);self.assertIn('salvar o link não conecta',message)


if __name__=='__main__':unittest.main()
