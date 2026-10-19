import io
import base64
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
import updates
import update_worker
from repository import normalize_repository


class ReleaseUpdaterTests(unittest.TestCase):
    def setUp(self):
        updates._notices.clear()
        self.settings = {'repository': 'https://github.com/Bl4ckF/fechamento_obra'}

    def test_notice_uses_release_and_version_not_git(self):
        with patch('updates.latest_release', return_value={'remote_version': '11.1.1', 'tag': 'v11.1.1', 'download_url': 'https://github.com/test.zip'}):
            new = updates.notice('/test', self.settings, '11.1.0')
            same = updates.notice('/test', self.settings, '11.1.0')
        self.assertTrue(new['available'])
        self.assertTrue(new['can_update'])
        self.assertEqual(same['mode'], 'release')

    def test_offline_check_does_not_report_false_update(self):
        with patch('updates.latest_release', side_effect=TimeoutError('offline')):
            result = updates.notice('/test', self.settings, '11.0.0')
        self.assertFalse(result['available'])
        self.assertIn('error', result)

    def test_no_new_version_does_not_launch(self):
        with patch('updates.check', return_value={'available': False}):
            result = updates.apply('/test', self.settings, '11.1.0')
        self.assertFalse(result['started'])

    def test_release_check_is_independent_of_git_and_record_sync(self):
        release={'tag_name':'v11.2.0','assets':[{'name':'Fechamento.zip','browser_download_url':'https://github.com/Bl4ckF/fechamento_obra/releases/download/v11.2.0/Fechamento.zip'}]}
        with patch('updates.urlopen',return_value=io.BytesIO(json.dumps(release).encode())),patch('updates.subprocess.run') as command:
            result=updates.notice('/modified-checkout',dict(self.settings,sync_enabled=True),'11.1.0',force=True)
        command.assert_not_called()
        self.assertTrue(result['can_update']);self.assertEqual(result['remote_version'],'11.2.0')

    def test_private_or_missing_repository_is_not_reported_as_up_to_date(self):
        with patch('updates.github_json',side_effect=HTTPError('https://api.github.com/',404,'Not Found',{},None)):
            result=updates.notice('/test',self.settings,'11.1.0',force=True)
        self.assertFalse(result['can_update']);self.assertIn('autenticação',result['detail'])

    def test_repo_without_releases_updates_from_pinned_branch_commit(self):
        sha='a'*40
        version=base64.b64encode(b'{"version":"11.4.0"}').decode()
        replies=[HTTPError('https://api.github.com/',404,'Not Found',{},None),[],{'default_branch':'main'},
                 {'commit':{'sha':sha}},{'content':version}]
        with patch('updates.github_json',side_effect=replies) as request:
            result=updates.notice('/test',dict(self.settings,branch='main'),'11.3.0',force=True)
        self.assertNotIn('error',result);self.assertTrue(result['can_update'])
        self.assertEqual(result['mode'],'branch');self.assertEqual(result['remote_version'],'11.4.0')
        self.assertTrue(result['download_url'].endswith('/zipball/'+sha))
        self.assertTrue(request.call_args_list[-1].args[0].endswith('version.json?ref='+sha))

    def test_missing_branch_is_distinguished_from_missing_repository(self):
        missing=HTTPError('https://api.github.com/',404,'Not Found',{},None)
        with patch('updates.github_json',side_effect=[missing,[],{'default_branch':'main'},missing]):
            result=updates.notice('/test',dict(self.settings,branch='nome-errado'),'11.3.0',force=True)
        self.assertFalse(result['available']);self.assertIn('Repositório encontrado',result['detail']);self.assertIn('branch',result['detail'])

    def test_missing_version_is_distinguished_from_missing_repository(self):
        missing=HTTPError('https://api.github.com/',404,'Not Found',{},None)
        with patch('updates.github_json',side_effect=[missing,[],{'default_branch':'main'},{'commit':{'sha':'a'*40}},missing]):
            result=updates.notice('/test',self.settings,'11.3.0',force=True)
        self.assertFalse(result['available']);self.assertIn('falta version.json',result['detail'])

    def test_restarted_sequence_uses_published_tags_instead_of_old_branch_number(self):
        missing=HTTPError('https://api.github.com/',404,'Not Found',{},None)
        tags=[{'name':'v1.3.0','commit':{'sha':'a'*40}}]
        with patch('updates.github_json',side_effect=[missing,tags]) as request:
            result=updates.notice('/test',self.settings,'1.3.1',force=True)
        self.assertFalse(result['available']);self.assertEqual(result['remote_version'],'1.3.0')
        self.assertEqual(result['mode'],'tag');self.assertEqual(request.call_count,2)
        self.assertNotIn('error',result)

    def test_new_tag_in_current_sequence_is_available_and_pinned(self):
        missing=HTTPError('https://api.github.com/',404,'Not Found',{},None)
        tags=[{'name':'v1.3.0','commit':{'sha':'a'*40}},{'name':'v1.3.2','commit':{'sha':'b'*40}}]
        with patch('updates.github_json',side_effect=[missing,tags]):
            result=updates.notice('/test',self.settings,'1.3.1',force=True)
        self.assertTrue(result['can_update']);self.assertEqual(result['remote_version'],'1.3.2')
        self.assertTrue(result['download_url'].endswith('/zipball/'+'b'*40))

    def test_cache_distinguishes_configured_branch(self):
        release={'remote_version':'11.4.0','tag':'v11.4.0','download_url':'https://github.com/test.zip'}
        with patch('updates.latest_release',return_value=release) as check:
            updates.notice('/test',dict(self.settings,branch='main'),'11.3.0')
            updates.notice('/test',dict(self.settings,branch='test'),'11.3.0')
        self.assertEqual(check.call_count,2)

    def test_normalizes_links_without_treating_release_or_tree_as_repository(self):
        expected='https://github.com/Bl4ckF/fechamento_obra'
        for link in ('Bl4ckF/fechamento_obra','github.com/Bl4ckF/fechamento_obra',expected+'.git/',expected+'/tree/main?tab=readme',expected+'/releases/tag/v11.2.0'):
            self.assertEqual(normalize_repository(link),expected)
        for link in ('https://github.com.evil.test/a/b','https://secret@github.com/a/b','file:///tmp/repo','https://github.com/owner','https://github.com/a/..'):
            with self.assertRaises(ValueError):normalize_repository(link)

    def test_branch_download_uses_github_archive_media_type(self):
        binary=io.BytesIO()
        with zipfile.ZipFile(binary,'w') as archive:archive.writestr('example.txt','programa')
        class Response(io.BytesIO):
            def geturl(self):return 'https://codeload.github.com/example/project/zip/123'
        with tempfile.TemporaryDirectory() as folder,patch('updates.urlopen',return_value=Response(binary.getvalue())) as request:
            target=Path(folder)/'programa.zip'
            updates.download_release('https://api.github.com/repos/example/project/zipball/'+'a'*40,target)
            self.assertTrue(zipfile.is_zipfile(target))
            self.assertEqual(request.call_args.args[0].get_header('Accept'),'application/vnd.github+json')

    def test_reject_version_mismatch_or_path_traversal(self):
        with tempfile.TemporaryDirectory() as t:
            archive = Path(t) / 'release.zip'
            with zipfile.ZipFile(archive, 'w') as z:
                for f in ('app.py', 'updates.py', 'INICIAR.bat'):
                    z.writestr('repo/' + f, f)
                z.writestr('repo/version.json', '{"version":"11.0.0"}')
            with self.assertRaisesRegex(ValueError, 'versão'):
                updates.valid_archive(archive, '11.1.0')
            with zipfile.ZipFile(archive, 'a') as z: z.writestr('repo/../../outside.txt', 'bad')
            with self.assertRaisesRegex(ValueError, 'inseguro'):
                update_worker.validate(archive, '11.0.0')

    def test_install_preserves_data_git_runtime_and_restores_no_replacements_on_malformed_zip(self):
        with tempfile.TemporaryDirectory() as t:
            root, outer = Path(t) / 'installed', Path(t) / 'temp'
            root.mkdir(); outer.mkdir()
            (root / 'dados').mkdir(); (root / 'dados' / 'fechamento.sqlite3').write_bytes(b'USER DATA')
            (root / '.git').mkdir(); (root / '.git' / 'HEAD').write_text('local')
            (root / 'runtime').mkdir(); (root / 'runtime' / 'python.exe').write_text('runtime')
            (root / 'app.py').write_text('old')
            archive = outer / 'release.zip'
            with zipfile.ZipFile(archive, 'w') as z:
                for path, data in {
                    'repo/app.py': 'new', 'repo/updates.py': 'new updater', 'repo/update_worker.py': 'worker',
                    'repo/INICIAR.bat': 'start app', 'repo/version.json': '{"version":"11.1.0"}',
                    'repo/dados/fechamento.sqlite3': 'BAD', 'repo/.git/HEAD': 'BAD',
                    'repo/runtime/python.exe': 'BAD', 'repo/web/main.js': 'updated web'
                }.items(): z.writestr(path, data)
            self.assertEqual(updates.valid_archive(archive, '11.1.0'), 'repo/')
            files = update_worker.install(root, archive, '11.1.0')
            self.assertEqual(files, 6)
            self.assertEqual((root / 'app.py').read_text(), 'new')
            self.assertEqual((root / 'web' / 'main.js').read_text(), 'updated web')
            self.assertEqual((root / 'dados' / 'fechamento.sqlite3').read_bytes(), b'USER DATA')
            self.assertEqual((root / '.git' / 'HEAD').read_text(), 'local')
            self.assertEqual((root / 'runtime' / 'python.exe').read_text(), 'runtime')

if __name__ == '__main__': unittest.main()
