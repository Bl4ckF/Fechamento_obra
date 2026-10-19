import copy
import unittest
from drawing import clean_drawing, symbol_catalog


class DrawingTests(unittest.TestCase):
    def test_original_pdf_preserved_without_vector_lines(self):
        ref='a'*64+'.png';pdf='b'*64+'.pdf'
        doc={'version':1,'objects':[],'background_ref':ref,'background_source':{'kind':'pdf','name':'texto.pdf','page':1},'pdf_source_ref':pdf,'pdf_lines':[]}
        saved=clean_drawing(doc,{ref,pdf})
        self.assertEqual(saved['pdf_source_ref'],pdf)
        self.assertEqual(clean_drawing(saved,{ref,pdf}),saved)
    def setUp(self):
        self.doc={'version':1,'objects':[{'id':'line1','type':'line','x1':10,'y1':20,'x2':300,'y2':400,'color':'#ff0000','width':8,'dash':'dashed','arrow':'both'},{'id':'label','type':'text','x1':60,'y1':80,'text':'Ponto 1','size':28,'color':'#123456'}]}
    def test_custom_lines_text_and_style_survive_roundtrip(self):
        result=clean_drawing(self.doc)
        self.assertEqual(clean_drawing(result),result)
        self.assertEqual(result['objects'][0]['dash'],'dashed')
        self.assertEqual(result['objects'][0]['arrow'],'both')
        self.assertEqual(result['objects'][1]['text'],'Ponto 1')
    def test_network_symbols_and_properties_survive_roundtrip(self):
        catalog=symbol_catalog()['symbols']
        self.assertEqual(len({s['id'] for s in catalog}),len(catalog))
        self.assertEqual(len([s for s in catalog if s['group']=='Identificação de estruturas']),51)
        for entry in catalog:
            doc={'version':1,'objects':[{'id':'sym_test','type':'symbol','symbol_id':entry['id'],
                 'x1':100,'y1':200,'size':90,'rotation':-45,'color':'#123456','status':'retirar','label':'P1','opaque':True}]}
            normalized=clean_drawing(doc)
            self.assertEqual(clean_drawing(normalized),normalized)
            self.assertEqual(normalized['objects'][0]['symbol_id'],entry['id'])
            self.assertTrue(normalized['objects'][0]['opaque'])
        for change in [{'symbol_id':'unknown'},{'status':'javascript'},{'size':0},{'rotation':float('inf')},{'x1':-1}]:
            bad=copy.deepcopy(doc);bad['objects'][0].update(change)
            with self.assertRaises(ValueError):clean_drawing(bad)

    def test_invalid_geometry_and_unavailable_background_rejected(self):
        for key,value in [('x1',-1),('y2',900),('width',100),('color','url(javascript:bad)')]:
            doc=copy.deepcopy(self.doc);doc['objects'][0][key]=value
            with self.assertRaises(ValueError):clean_drawing(doc)
        with self.assertRaises(ValueError):clean_drawing({**self.doc,'background_ref':'a'*64+'.png'},set())
    def test_freehand_coordinates_remain_editable(self):
        points=[{'x':i,'y':i/2} for i in range(100)]
        result=clean_drawing({'version':1,'objects':[{'id':'pen','type':'pen','points':points}]})
        self.assertEqual(result['objects'][0]['points'],points)
    def test_pdf_page_source_background_and_ink_survive_backup(self):
        ref='a'*64+'.png';source={'kind':'pdf','name':'Planta.pdf','page':3,'rotation':90}
        doc={**self.doc,'background_ref':ref,'background_source':source}
        result=clean_drawing(doc,{ref})
        self.assertEqual(result['background_source'],source)
        self.assertEqual(result['background_ref'],ref)
        self.assertEqual(len(result['objects']),2)

    def pdf_doc(self):
        ref='a'*64+'.png';clean='b'*64+'.png'
        return {'version':1,'background_ref':ref,'background_source':{'kind':'pdf','name':'Planta.pdf','page':1},
            'pdf_text_background_ref':clean,'pdf_texts':[{'id':'pdf_0','text':'Original','x1':40,'y1':50,'size':16,'rotation':90,'font':'Arial','box':{'x':38,'y':30,'w':25,'h':110},'text_width':100}],
            'objects':[{'id':'pdf_0','type':'text','pdf_text_id':'pdf_0','text':'Corrigido','x1':80,'y1':90,'size':20,'rotation':90,'font':'Courier New','bold':True}]}

    def test_pdf_text_edits_survive_roundtrip_and_deletion(self):
        doc=self.pdf_doc();refs={doc['background_ref'],doc['pdf_text_background_ref']}
        clean=clean_drawing(doc,refs)
        self.assertEqual(clean_drawing(clean,refs),clean)
        self.assertEqual(clean['pdf_texts'][0]['text'],'Original')
        self.assertEqual(clean['objects'][0]['text'],'Corrigido')
        self.assertEqual(clean['objects'][0]['rotation'],90)
        clean['objects'][0]['text']=''
        self.assertEqual(clean_drawing(clean,refs)['objects'][0]['text'],'')
        clean['objects']=[]
        self.assertEqual(clean_drawing(clean,refs)['pdf_texts'][0]['text'],'Original')

    def test_missing_pdf_layer_invalid_reference_and_box_rejected(self):
        doc=self.pdf_doc()
        with self.assertRaises(ValueError):clean_drawing(doc,{doc['background_ref']})
        for edit in [lambda d:d['objects'][0].update(pdf_text_id='pdf_99'),lambda d:d['pdf_texts'][0]['box'].update(x=1199,w=30),lambda d:d['objects'][0].update(font='url(bad)'),lambda d:d['pdf_texts'].append(d['pdf_texts'][0])]:
            bad=copy.deepcopy(doc);edit(bad)
            with self.assertRaises(ValueError):clean_drawing(bad)


if __name__=='__main__':unittest.main()
