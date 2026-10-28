"""Local feature checks and allowlisted per-user installers."""
import copy
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from ocr_runtime import python_path

ROOT=Path(__file__).resolve().parent
INSTALLERS={'poda':'instalar_poda.py','ocr':'instalar_leitor_fotos.py'}
LOCK=threading.RLock()
CHECK_LOCK=threading.Lock()
_CACHE=None
_CHECKED=0
_JOB={'state':'idle','feature':None,'log':[],'message':''}


def probe(command):
    try:
        r=subprocess.run(command,capture_output=True,timeout=40,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        return r.returncode==0
    except (OSError,subprocess.SubprocessError):return False


def checks(force=False):
    global _CACHE,_CHECKED
    with CHECK_LOCK:
        if _CACHE is not None and not force and time.monotonic()-_CHECKED<60:return copy.deepcopy(_CACHE)
        pillow=probe([sys.executable,'-c',"from PIL import Image,ImageOps; Image.new('RGB',(2,2)).resize((1,1))"])
        pdf=probe([sys.executable,'-c',"import io; from reportlab.pdfgen.canvas import Canvas; c=Canvas(io.BytesIO()); c.drawString(10,10,'teste'); c.save()"])
        executable=python_path()
        ocr=probe([str(executable if executable.is_file() else sys.executable),str(ROOT/'tools/ocr_worker.py'),'--check']) if pillow else False
        assets=all((ROOT/name).is_file() for name in ['web/vendor/pdfjs/pdf.min.mjs','web/vendor/pdfjs/pdf.worker.min.mjs','web/vendor/pdf-lib/pdf-lib.min.js'])
        _CACHE=[{'id':'core','name':'Programa e fechamento','ready':sys.version_info>=(3,9),'installable':False,'detail':'Python '+sys.version.split()[0]+' · cadastros e books de obras.'},
                {'id':'croqui','name':'Editor de croqui PDF','ready':assets,'installable':False,'detail':'Arquivos do editor disponíveis.' if assets else 'Arquivos do editor ausentes. Reaplique uma atualização válida do programa.'},
                {'id':'poda','name':'Books de Poda e LF','ready':pillow and pdf,'installable':True,'detail':'Pillow e ReportLab verificados.' if pillow and pdf else 'Instale os recursos de imagens e geração de PDF.'},
                {'id':'ocr','name':'Leitor de fotos Timestamp','ready':pillow and ocr,'installable':True,'detail':'Imagens e motor OCR verificados.' if pillow and ocr else 'Instale o leitor e seu ambiente Python compatível.'}]
        _CHECKED=time.monotonic()
        return copy.deepcopy(_CACHE)


def status(force=False):
    with LOCK:job=copy.deepcopy(_JOB)
    return {'features':checks(force),'job':job}


def running():
    with LOCK:return _JOB['state']=='running'


def _install(feature):
    global _CACHE
    try:
        env={**os.environ,'PYTHONIOENCODING':'utf-8','PYTHONUNBUFFERED':'1','PIP_NO_INPUT':'1'}
        process=subprocess.Popen([sys.executable,'-u',str(ROOT/'tools'/INSTALLERS[feature])],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',env=env,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        for line in process.stdout:
            with LOCK:_JOB['log']=(_JOB['log']+[line.rstrip()[:1000]])[-80:]
        code=process.wait()
        # A successful pip exit alone is insufficient: validate the actual feature.
        features=checks(force=True)
        ready=next(item['ready'] for item in features if item['id']==feature)
        with LOCK:
            _JOB['state']='success' if code==0 and ready else 'error'
            _JOB['message']='Recursos instalados e verificados. Se esta operação não iniciou antes, reabra a página quando terminar seu trabalho.' if _JOB['state']=='success' else 'Não foi possível concluir a instalação ou validar o recurso. Consulte os detalhes. Confira internet, permissões e a mensagem do instalador.'
    except Exception:
        with LOCK:_JOB.update(state='error',message='Não foi possível executar o instalador. Confira permissões e os arquivos do programa.')


def start(feature):
    if not isinstance(feature,str) or feature not in INSTALLERS:raise ValueError('Recurso inválido para instalação.')
    with LOCK:
        if running():raise ValueError('Uma instalação já está em andamento. Aguarde a conclusão.')
        _JOB.update(state='running',feature=feature,log=[],message='Instalando. Mantenha o programa aberto. É necessário acesso à internet.')
        threading.Thread(target=_install,args=(feature,),daemon=True).start()
    return {'started':True}
