import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('installer',Path(__file__).resolve().parents[1]/'tools/instalar_leitor_fotos.py')
installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)

class OCRInstallerTests(unittest.TestCase):
 def test_version_guard_rejects_python314(self):
  with patch.object(installer.subprocess,'run',return_value=subprocess.CompletedProcess([],1,'C:/python314.exe\n')):
   self.assertIsNone(installer.compatible(['python']))
  self.assertIn('(3,13)',installer.PROBE)
 def test_existing_compatible_interpreter(self):
  with tempfile.NamedTemporaryFile() as f,patch.object(installer.subprocess,'run') as run:
   run.return_value=subprocess.CompletedProcess([],0,f.name+'\n')
   self.assertEqual(installer.compatible(['py','-3.12']),f.name)
   self.assertEqual(run.call_args.kwargs['env']['PYTHON_MANAGER_AUTOMATIC_INSTALL'],'false')
 def test_search_uses_312_after_incompatible_current(self):
  with patch.object(installer,'compatible',side_effect=[None,'compatible.exe']):
   self.assertEqual(installer.find_python(),'compatible.exe')
 def test_manager_failure_is_not_success(self):
  with patch.object(installer,'compatible',return_value=None),patch.object(installer.subprocess,'run',side_effect=FileNotFoundError):
   with self.assertRaisesRegex(RuntimeError,'Não foi possível'):installer.find_python()
 def test_worker_subprocess_no_shell_and_timeout(self):
  import photo_reader
  from PIL import Image
  with tempfile.NamedTemporaryFile() as f,patch.object(photo_reader,'python_path',return_value=Path(f.name)),patch.object(photo_reader.subprocess,'run') as run:
   run.return_value=subprocess.CompletedProcess([],0,b'{"text":"Obra:123","scores":[],"warnings":[]}')
   self.assertEqual(photo_reader.run_ocr(Image.new('RGB',(12,12)))[0],'Obra:123')
   self.assertEqual(run.call_args.kwargs['timeout'],120)
   self.assertNotIn('shell',run.call_args.kwargs)
