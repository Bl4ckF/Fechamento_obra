import io
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

    def test_missing_or_private_release_is_not_reported_as_up_to_date(self):
        with patch('updates.latest_release',side_effect=HTTPError('https://api.github.com/',404,'Not Found',{},None)):
            result=updates.notice('/test',self.settings,'11.1.0',force=True)
        self.assertFalse(result['can_update']);self.assertIn('Release pública',result['error']);self.assertIn('privados',result['detail'])

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
