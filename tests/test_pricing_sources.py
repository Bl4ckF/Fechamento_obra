import copy
import hashlib
import json
import re
import tempfile
import unittest
from decimal import Decimal, ROUND_HALF_UP, localcontext
from pathlib import Path
from unittest.mock import patch

import app
import engine
from book_report import book_html, labor_totals, materials_report_html
from pricing import clean_price, line_total, money, service_price
from test_app import service
from tools.importar_bases import extract, read_workbook


class SourceTests(unittest.TestCase):
    def test_only_supplied_workbooks_generate_entire_catalog(self):
        root=engine.ROOT
        self.assertEqual({p.name for p in (root/'fontes').iterdir()},{'Mão de obra.xlsx','MATERIAL.xlsm'})
        catalog,bases=extract(root)
        self.assertEqual(catalog,json.loads((root/'data/catalogos.json').read_text()))
        self.assertEqual(bases,json.loads((root/'data/composicoes_material.json').read_text()))
        self.assertFalse((root/'data/composicoes_material41.json').exists())
        self.assertEqual(bases['equipment_references'],[])
        for name,sha in catalog['source_sha256'].items():
            self.assertEqual(sha,hashlib.sha256((root/'fontes'/name).read_bytes()).hexdigest())
        workbook=read_workbook(root/'fontes/MATERIAL.xlsm')
        expected={(r['B'],r['C'],r['D']) for row,r in workbook['Lista de Materiais'].items() if row>1}
        self.assertEqual(expected,{(m['code'],m['description'],m['unit']) for m in catalog['materials']})
        self.assertEqual({m['code'] for m in bases['extra_materials']},{'90442'})
        self.assertEqual({m['id'] for m in bases['extra_materials']},{'base41_90442'})
        self.assertTrue(all(m['unit'] for m in catalog['materials']))

    def test_all_prices_match_saved_workbook_cells_without_early_rounding(self):
        workbook=read_workbook(engine.ROOT/'fontes/Mão de obra.xlsx')
        priced=0
        for labor in engine.LABOR.values():
            source=labor['price_source'];col='J' if labor['sheet']=='C&M (LM)' else 'I'
            if labor['sheet']=='PAGAMENTOS ESPECIAIS':
                self.assertIsNone(labor['unit_price']);self.assertEqual(source['status'],'nao_informado');continue
            raw=workbook[labor['sheet']][labor['row']][col]
            self.assertEqual(source['cell'],col+str(labor['row']))
            if raw.startswith('#'):
                self.assertIsNone(labor['unit_price']);self.assertEqual(source['status'],'erro_na_origem')
            else:
                self.assertEqual(Decimal(labor['unit_price']),Decimal(raw));priced+=1
        self.assertEqual(priced,723)
        self.assertEqual(len(engine.CATALOG['price_issues']),10)
        self.assertEqual(Decimal(engine.LABOR['s1r29']['unit_price']),Decimal('1028.3247272727274'))


class PriceTests(unittest.TestCase):
    def test_full_source_precision_and_quantity_are_used_before_rounding(self):
        for lid,qty in [('s1r4','3'),('s1r29','123.456789'),('s1r76','999999999.999999')]:
            amount=engine.LABOR[lid]['unit_price']
            with localcontext() as ctx:
                ctx.prec=60
                expected=(Decimal(amount)*Decimal(qty)).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
            self.assertEqual(line_total(qty,amount),expected)
        self.assertEqual(line_total('3',engine.LABOR['s1r4']['unit_price']),Decimal('869.81'))
        self.assertEqual(line_total('1','0.005'),Decimal('0.01'))
        self.assertEqual(money('1234.567890123',unit=True),'1.234,56789')
        self.assertEqual(money('1234.565'),'1.234,57')

    def test_unit_prices_cannot_be_overridden_by_service_input(self):
        s=service();s.update(unit_price='1',price_source={'file':'outro.xlsx'})
        clean=engine.clean_service(s)
        self.assertEqual(clean['unit_price'],engine.LABOR[s['labor_id']]['unit_price'])
        self.assertEqual(clean['price_source']['file'],'Mão de obra.xlsx')
        self.assertEqual(engine.clean_profile(s)['unit_price'],clean['unit_price'])

    def test_aggregation_keeps_operation_scope_and_price_separate(self):
        items=engine.calculate([service(quantity='0.1'),service(quantity='0.2'),service('s1r6',quantity='1')])['services']
        different_price=dict(items[0],unit_price='100')
        totals=labor_totals(items+[different_price])
        self.assertEqual(len(totals),3)
        installed=next(s for s in totals if s['unit_price']==items[0]['unit_price'] and s['operation']=='INSTALAR')
        self.assertEqual(installed['quantity'],Decimal('0.3'))
        self.assertEqual(installed['total_price'],Decimal('86.98'))
        self.assertEqual({s['operation'] for s in totals},{'INSTALAR','RETIRAR'})

    def test_zero_missing_and_invalid_values_are_distinct(self):
        self.assertEqual(clean_price(0),'0');self.assertIsNone(clean_price(None))
        self.assertEqual(line_total('10','0'),Decimal('0.00'))
        self.assertIsNone(line_total('10',None))
        for value in ['NaN','Infinity','-1','1e999','1e-999','#REF!','']:
            with self.assertRaises(ValueError):clean_price(value)

    def test_legacy_lookup_requires_matching_identity_and_preserves_missing_snapshot(self):
        s=engine.clean_service(service());expected=s.pop('unit_price');s.pop('price_source')
        self.assertEqual(service_price(s,engine.LABOR)[0],expected)
        self.assertEqual(service_price(s,engine.LABOR)[1]['legacy_lookup'],'true')
        self.assertIsNone(service_price(dict(s,scope='OUTRO'),engine.LABOR)[0])
        self.assertIsNone(service_price(dict(s,unit_price=None),engine.LABOR)[0])


class PriceReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.previous=app.DATA_DIR,app.DB
        app.DATA_DIR=Path(self.tmp.name);app.DB=app.DATA_DIR/'fechamento.sqlite3'
    def tearDown(self):
        app.DATA_DIR,app.DB=self.previous;self.tmp.cleanup()
    def job(self,items=None):
        return app.save_job({'work_order':'VERIFICAÇÃO','responsible':'Equipe de teste','services':items or [service()]})

    def test_prices_only_appear_in_labor_total_pages(self):
        job=self.job();pdf=materials_report_html(job).decode()
        pages=re.findall(r'<article.*?</article>',pdf,re.S)
        self.assertEqual(len(pages),3)
        self.assertIn('Unitário (R$)',pages[0]);self.assertIn('869,81',pages[0])
        self.assertIn('R$ 869,81',pages[0])
        for page in pages[1:]:self.assertNotIn('R$',page);self.assertNotIn('869,81',page)
        for report in [book_html(job).decode(),app.report_csv(job).decode()]:
            self.assertNotIn('R$',report);self.assertNotIn('869,81',report);self.assertNotIn('289,9356',report)

    def test_missing_prices_show_partial_total_instead_of_zero(self):
        special=next(s for s in engine.LABOR.values() if s['sheet']=='PAGAMENTOS ESPECIAIS')
        job=self.job([service(),service(special['id']),service('s1r280')])
        pdf=materials_report_html(job).decode()
        for label in ['Subtotal com valor informado','R$ 869,81','2 linha(s) sem valor válido','Não informado','Erro na origem']:
            self.assertIn(label,pdf)
        self.assertNotIn('Total da mão de obra</strong>',pdf)
        pdf=materials_report_html(self.job([service(special['id'])])).decode()
        self.assertIn('Sem valores informados',pdf);self.assertNotIn('R$ 0,00',pdf)

    def test_total_adds_rounded_lines_not_rounded_unit_values(self):
        job=self.job([service(quantity='1'),service('s1r6',quantity='1')])
        for item in job['result']['services']:item['unit_price']='0.005'
        pdf=materials_report_html(job).decode()
        self.assertIn('R$ 0,02',pdf)

    def test_book_observations_show_names_and_keep_manually_entered_notes(self):
        base=next(b for b in engine.BASES.values() if b['kind']=='structure' and b['params']=={'pole':'DT','structure':'N1'})
        job=self.job([dict(service(),point_id='p1',base_id=base['id']),dict(service('s1r6'),point_id='p1')])
        job['book']={'points':[{'id':'p1','number':'01','installed':'Conferido no local.','removed':'Recolhido pela equipe.','notes':'Referência digitada: 62256.','photos':[]}],'no_conductors':True}
        pdf=book_html(job).decode()
        installed=pdf.split('<h3>INSTALADO</h3>',1)[1].split('</p>',1)[0]
        removed=pdf.split('<h3>DESATIVADO</h3>',1)[1].split('</p>',1)[0]
        self.assertIn('Estrutura N1',installed);self.assertNotIn(engine.LABOR['s1r4']['description'],installed)
        self.assertIn(engine.LABOR['s1r6']['description'],' '.join(removed.split()))
        for text in [installed,removed]:
            self.assertNotIn(engine.LABOR['s1r4']['code'],text);self.assertNotIn('×',text);self.assertNotIn('R$',text)
        for text in ['Conferido no local.','Recolhido pela equipe.','Referência digitada: 62256.']:self.assertIn(text,' '.join(pdf.split()))

    def test_saved_prices_and_source_survive_catalog_changes_and_backup_restore(self):
        job=self.job();stored=copy.deepcopy(job['result']['services'][0])
        backup={'app':app.APP_ID,'schema':4,'profiles':[],'jobs':[job]}
        with patch.dict(engine.LABOR['s1r4'],unit_price='999'):
            self.assertIn('R$ 869,81',materials_report_html(job).decode())
            app.restore(backup)
            restored=next(j for j in app.records('jobs') if j['id']==job['id'])
            self.assertEqual(restored['result']['services'][0]['unit_price'],stored['unit_price'])
            self.assertEqual(restored['result']['services'][0]['price_source'],stored['price_source'])
            self.assertEqual(self.job()['result']['services'][0]['unit_price'],'999')
        bad=copy.deepcopy(backup);bad['jobs'][0]['result']['services'][0]['unit_price']='NaN'
        with self.assertRaises(ValueError):app.restore(bad)
        self.assertEqual(next(j for j in app.records('jobs') if j['id']==job['id'])['result']['services'][0]['unit_price'],stored['unit_price'])

    def test_old_backup_reports_current_price_as_consulted_not_historical(self):
        job=self.job()
        for s in job['result']['services']:s.pop('unit_price');s.pop('price_source')
        app.restore({'app':app.APP_ID,'schema':4,'profiles':[],'jobs':[job]})
        restored=next(j for j in app.records('jobs') if j['id']==job['id'])
        pdf=materials_report_html(restored).decode()
        self.assertIn('preços consultados na base atual',pdf);self.assertIn('R$ 869,81',pdf)


if __name__=='__main__':unittest.main()
