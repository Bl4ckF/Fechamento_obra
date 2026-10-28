"""Empacota os editores PDF/CAD já compilados, sem downloads do Trunk."""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('program',choices=('cadcraft','pdfcraft'))
    parser.add_argument('--wasm',type=Path,required=True)
    args=parser.parse_args()
    root=Path(__file__).resolve().parent.parent
    source=root.parent/args.program
    template=(source/'apps'/(args.program+'-web')/'index.html').read_text(encoding='utf-8')
    html,count=re.subn(r'<link\b(?=[^>]*\bdata-trunk\b)(?=[^>]*\brel=["\']rust["\'])[^>]*>', '',template,flags=re.I)
    if count!=1 or 'data-trunk' in html:
        raise ValueError('A página exige recursos adicionais; utilize o empacotador original.')
    if not args.wasm.is_file():raise ValueError('Módulo WebAssembly compilado não encontrado.')
    destination=root/'web'/'operations'/args.program
    with tempfile.TemporaryDirectory(prefix='engelmig-package-') as staging:
        output=Path(staging)
        subprocess.run(['wasm-bindgen','--target','web','--no-typescript','--out-name','editor','--out-dir',str(output),str(args.wasm)],check=True)
        operation=json.dumps(args.program)
        bootstrap="import init from './editor.js';\ninit().catch(error=>{parent.postMessage({type:"+operation+"+':failed',error:String(error)},location.origin);});\n"
        (output/'bootstrap.js').write_text(bootstrap,encoding='utf-8')
        html=html.replace('</body>','<script type="module" src="./bootstrap.js"></script></body>')
        (output/'index.html').write_text(html,encoding='utf-8')
        for notice in ('LICENSE-MIT','LICENSE-APACHE','NOTICE','ATTRIBUTION.md','ATTRIBUTION.toml'):
            if (source/notice).is_file():shutil.copy2(source/notice,output/notice)
        attribution=source/'ATTRIBUTION.toml'
        if attribution.is_file():
            for relative in set(re.findall(r'^licence_file\s*=\s*"([^"]+)"',attribution.read_text(encoding='utf-8'),re.M)):
                license_path=(source/relative).resolve()
                if not license_path.is_relative_to(source.resolve()) or not license_path.is_file():
                    raise ValueError('Licença de atribuição ausente ou fora dos fontes: '+relative)
                target=output/relative
                target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(license_path,target)
        shutil.copytree(output,destination,dirs_exist_ok=True)
    print(args.program+': módulo incorporado em '+str(destination))


if __name__=='__main__':main()
