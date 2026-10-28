"""Install an isolated OCR environment, including when the app uses Python 3.14."""
import os
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ocr_runtime import environment_path,python_path

PROBE="import sys,struct; print(sys.executable); sys.exit(0 if (3,9)<=sys.version_info[:2]<(3,13) and struct.calcsize('P')==8 else 1)"
PROBE_ENV={**os.environ,'PYTHON_MANAGER_AUTOMATIC_INSTALL':'false'}


def compatible(command):
    try:
        result=subprocess.run(command+['-c',PROBE],capture_output=True,text=True,timeout=30,env=PROBE_ENV)
        if result.returncode==0:
            path=Path(result.stdout.strip().splitlines()[-1])
            if path.is_file():return str(path)
    except (OSError,subprocess.SubprocessError,IndexError):pass
    return None


def find_python():
    for command in [[sys.executable],['py','-3.12'],['py','-3.11'],['py','-3.10'],['py','-3.9']]:
        found=compatible(command)
        if found:return found
    # Install Manager installs per user and coexists with the main Python.
    for manager in ['pymanager','py']:
        try:
            check=subprocess.run([manager,'install','--help'],capture_output=True,timeout=20,env=PROBE_ENV)
            if check.returncode:continue
            print('Baixando Python 3.12 pelo gerenciador oficial, para este usuário...',flush=True)
            result=subprocess.call([manager,'install','3.12'])
            if result:break
            found=compatible([manager,'-3.12']) or compatible(['py','-3.12'])
            if found:return found
        except (OSError,subprocess.SubprocessError):continue
    raise RuntimeError('Não foi possível obter Python compatível. Instale Python 3.12 de 64 bits para seu usuário (python.org), sem instalação para todos os usuários, e execute este BAT novamente. Se houver bloqueio corporativo, solicite ao TI.')


def main():
    print('Preparando leitor local em ambiente separado. Não é necessário remover Python 3.14.',flush=True)
    target=python_path()
    if not target.exists():
        source=find_python()
        subprocess.run([source,'-m','venv',str(environment_path())],check=True)
    if not compatible([str(target)]):raise RuntimeError('O ambiente do leitor não possui Python 3.9–3.12 de 64 bits. Instalação interrompida.')
    print('Instalando OCR no ambiente do leitor...',flush=True)
    subprocess.run([str(target),'-m','pip','install','--disable-pip-version-check','--prefer-binary','Pillow>=10,<14','rapidocr-onnxruntime==1.4.4'],check=True)
    subprocess.run([str(target),str(Path(__file__).with_name('ocr_worker.py')),'--check'],check=True)
    # The application still needs Pillow to display/process EXIF before OCR.
    command=[sys.executable,'-m','pip','install','--disable-pip-version-check','Pillow>=10,<14']
    if sys.prefix==sys.base_prefix:command.append('--user')
    subprocess.run(command,check=True)
    print('Leitor instalado e verificado. Reinicie o programa.',flush=True)
    return 0

if __name__=='__main__':
    try:sys.exit(main())
    except (RuntimeError,OSError,subprocess.SubprocessError) as error:
        print('FALHA: '+str(error),flush=True);sys.exit(1)
