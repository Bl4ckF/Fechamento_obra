import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import book
import records_sync
import updates
import update_security
import update_worker


class SecurityTests(unittest.TestCase):
    def test_records_repository_normalized_independently(self):
        config = book.clean_settings({'records_repository': 'Bl4ckF/materiais'})
        self.assertEqual(config['records_repository'], 'https://github.com/Bl4ckF/materiais')
        self.assertEqual(config['repository'], book.DEFAULT_SETTINGS['repository'])
        with tempfile.TemporaryDirectory() as directory:
            sync = records_sync.RecordSync(directory, lambda: config, lambda: [], lambda x: None)
            self.assertEqual(sync.status()['repository'], config['records_repository'])

    def test_legacy_records_repository_preserved(self):
        config = book.clean_settings({})
        with tempfile.TemporaryDirectory() as directory:
            sync = records_sync.RecordSync(directory, lambda: config, lambda: [], lambda x: None)
            self.assertEqual(sync.status()['repository'], config['repository'])

    def test_invalid_records_repository_refused(self):
        with self.assertRaises(ValueError):
            book.clean_settings({'records_repository': 'https://token@github.com/user/repo'})

    def test_update_hosts(self):
        for url in ['http://github.com/u/r', 'https://github.com.evil.test/a', 'https://evil.test/a', 'https://x@github.com/a', 'https://github.com:444/a']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                update_security.github_url(url)
        self.assertEqual(update_security.github_url('https://github.com/u/r'), 'https://github.com/u/r')

    def test_unsigned_release_cannot_launch(self):
        with patch('updates.check',return_value={'available':True,'remote_version':'1.3.9'}), patch('updates.subprocess.Popen') as launch:
            with self.assertRaisesRegex(ValueError,'assinatura'):
                updates.apply('/tmp', {}, '1.3.7')
        launch.assert_not_called()

    def test_signed_release_asset_discovery(self):
        payload={'tag_name':'v1.3.9','assets':[{'name':'update.zip','browser_download_url':'https://github.com/a.zip'},
                 {'name':'update.zip.sig.json','browser_download_url':'https://github.com/a.sig.json'}]}
        with patch('updates.github_json',return_value=payload):
            self.assertEqual(updates.latest_release({'repository':'x/y'})['signature_url'],'https://github.com/a.sig.json')

    def test_missing_key_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder, self.assertRaisesRegex(ValueError,'Chave pública'):
            update_security.verify('unused', {}, '1.3.9', folder)

    def test_tamper_detected_before_crypto(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'security').mkdir();(root/'security/update-public.xml').write_text('public')
            archive=root/'a.zip';archive.write_bytes(b'changed')
            with patch('update_security.verify_rsa_windows') as run, self.assertRaisesRegex(ValueError,'alterado'):
                update_security.verify(archive,{'algorithm':'RSA-SHA256','version':'1.3.9','sha256':'0'*64},'1.3.9',root)
            run.assert_not_called()

    def archive(self, folder, extra=None):
        archive=Path(folder)/'release.zip'
        with zipfile.ZipFile(archive,'w') as z:
            for name in ['app.py','updates.py','INICIAR.bat']:z.writestr('repo/'+name,'new')
            z.writestr('repo/version.json',json.dumps({'version':'1.3.9'}))
            if extra:z.writestr('repo/'+extra,'bad')
        return archive

    def test_windows_unsafe_paths_and_duplicates(self):
        for extra in ['APP.PY','a:stream','NUL.txt','web/file.','web/file ']:
            with self.subTest(extra=extra), tempfile.TemporaryDirectory() as folder:
                archive=self.archive(folder,extra)
                with self.assertRaises(ValueError):update_worker.validate(archive,'1.3.9')

    def test_worker_refuses_modified_archive_and_downgrade(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'app';root.mkdir();(root/'app.py').write_text('old')
            archive=self.archive(folder)
            with self.assertRaisesRegex(ValueError,'mudou'):update_worker.install(root,archive,'1.3.9','0'*64)
            (root/'version.json').write_text('{"version":"1.3.9"}')
            with self.assertRaisesRegex(ValueError,'antiga'):update_worker.install(root,archive,'1.3.9')
            self.assertEqual((root/'app.py').read_text(),'old')

    def test_worker_rejects_symlink_escape(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'app';root.mkdir();(root/'app.py').write_text('old')
            outside=Path(folder)/'outside';outside.mkdir();(root/'web').symlink_to(outside,target_is_directory=True)
            archive=self.archive(folder,'web/test.js')
            with self.assertRaisesRegex(ValueError,'fora da instalação'):update_worker.install(root,archive,'1.3.9')
            self.assertEqual(list(outside.iterdir()),[])

    def test_rollback_restores_existing_and_removes_new_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'app';root.mkdir();(root/'app.py').write_text('old')
            archive=self.archive(folder,'web/test.js')
            real_replace=update_worker.os.replace
            def fail(source, dest):
                if Path(dest).name=='version.json':raise OSError('disk failure')
                return real_replace(source,dest)
            with patch('update_worker.os.replace',side_effect=fail), self.assertRaises(OSError):
                update_worker.install(root,archive,'1.3.9')
            self.assertEqual((root/'app.py').read_text(),'old')
            self.assertFalse((root/'updates.py').exists())
            self.assertFalse((root/'INICIAR.bat').exists())

class CngAdapterTests(unittest.TestCase):
    def test_public_key_blob_matches_uploaded_key(self):
        import base64, struct, xml.etree.ElementTree as ET
        path=Path(update_security.__file__).parent/'security/update-public.xml'
        xml=ET.fromstring(path.read_bytes())
        blob=update_security.public_blob(path)
        self.assertEqual(struct.unpack('<6I',blob[:24]),(0x31415352,3072,3,384,0,0))
        self.assertEqual(blob[24:27],b'\x01\x00\x01')
        self.assertEqual(blob[27:],base64.b64decode(xml.findtext('Modulus')))

    def test_native_call_hash_and_failure_propagation(self):
        import ctypes
        from types import SimpleNamespace
        from unittest.mock import Mock
        key=Path(update_security.__file__).parent/'security/update-public.xml'
        message=b'Engelmig-update-v1\n1.3.9\n' + b'a'*64 + b'\n'
        signature=b's'*384
        def opened(pointer,*args): pointer._obj.value=11; return 0
        def imported(algorithm,unused,kind,pointer,buffer,size,flags):
            self.assertEqual(kind,'RSAPUBLICBLOB')
            self.assertEqual(ctypes.string_at(buffer,size),update_security.public_blob(key))
            pointer._obj.value=12;return 0
        def checked(handle,padding,digest,digest_len,sig,sig_len,flags):
            self.assertEqual(padding._obj.pszAlgId,'SHA256')
            self.assertEqual(flags,2)
            self.assertEqual(ctypes.string_at(digest,digest_len),hashlib.sha256(message).digest())
            self.assertEqual(ctypes.string_at(sig,sig_len),signature)
            return 0
        api=SimpleNamespace(BCryptOpenAlgorithmProvider=Mock(side_effect=opened),
              BCryptImportKeyPair=Mock(side_effect=imported),BCryptVerifySignature=Mock(side_effect=checked),
              BCryptDestroyKey=Mock(return_value=0),BCryptCloseAlgorithmProvider=Mock(return_value=0))
        with patch.object(ctypes,'WinDLL',return_value=api,create=True):
            update_security.verify_rsa_windows(key,message,signature)
            api.BCryptVerifySignature.side_effect=None;api.BCryptVerifySignature.return_value=-1073700864
            with self.assertRaisesRegex(ValueError,'recusada'):
                update_security.verify_rsa_windows(key,message,signature)
        self.assertEqual(api.BCryptDestroyKey.call_count,2)
        self.assertEqual(api.BCryptCloseAlgorithmProvider.call_count,2)
