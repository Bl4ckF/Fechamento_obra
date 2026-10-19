"""Reúne exportações da equipe numa base distribuível com a próxima versão."""
import argparse
import glob
import json
import os
import sqlite3
from pathlib import Path
import learning


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('arquivos',nargs='+',help='Exportações JSON de registros ou padrões; aceita *.json.')
    parser.add_argument('--saida',default=str(Path(__file__).parent/'data/padroes_materiais.json'))
    args=parser.parse_args();paths=[]
    for name in args.arquivos:
        matches=glob.glob(name)
        if not matches:parser.error('Arquivo não encontrado: '+name)
        paths.extend(Path(p) for p in matches)
    with sqlite3.connect(':memory:') as db:
        learning.ensure(db)
        for path in dict.fromkeys(paths):learning.import_records(db,json.loads(path.read_text(encoding='utf-8-sig')))
        result=learning.export_patterns(db)
    dest=Path(args.saida);dest.parent.mkdir(parents=True,exist_ok=True)
    temp=dest.with_suffix('.tmp');temp.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');os.replace(temp,dest)
    print(f"Base preparada: {dest}\n{len(result['patterns'])} padrão(ões), {len(result['samples'])} ocorrência(s).")
    print('Os campos de responsável, obra, observações e fotos não são incluídos.')


if __name__=='__main__':main()
