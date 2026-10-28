"""Install optional PDF/image dependencies in the current user's Python."""
import importlib.util
import subprocess
import sys

def main():
    missing=[]
    for module,package in [('PIL.Image','Pillow>=10,<14'),('reportlab.pdfgen.canvas','reportlab>=4,<5')]:
        try:__import__(module)
        except (ImportError,OSError):missing.append(package)
    if not missing:
        print('Recursos de Poda já instalados.');return 0
    print('Instalando recursos de Poda para este Python. É necessário acesso à internet.',flush=True)
    args=[sys.executable,'-m','pip','install','--disable-pip-version-check']
    if sys.prefix==sys.base_prefix:args.append('--user')
    args+=missing
    return subprocess.call(args)

if __name__=='__main__':sys.exit(main())
