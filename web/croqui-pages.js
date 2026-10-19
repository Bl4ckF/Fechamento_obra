'use strict';
(() => {
 const id=()=> 'croqui_'+crypto.randomUUID().replaceAll('-','');
 function selection(mode,value,total,current=1){
  if(!Number.isInteger(total)||total<1)throw Error('PDF sem páginas disponíveis.');
  let values=[];
  if(mode==='all'){if(total>100)throw Error('Importe até 100 páginas por vez. Escolha um intervalo.');values=Array.from({length:total},(_,i)=>i+1);}
  else if(mode==='single')values=[Number(current)];
  else if(mode==='range'){
   if(!String(value).trim())throw Error('Informe as páginas, por exemplo: 2-5 ou 1,3,7-9.');
   for(const part of String(value).split(',')){
    const match=part.trim().match(/^(\d+)\s*(?:-\s*(\d+))?$/);if(!match)throw Error('Intervalo inválido. Use 2-5 ou 1,3,7-9.');
    const start=Number(match[1]),end=Number(match[2]||match[1]);
    if(start<1||end>total||end<start)throw Error('Escolha páginas entre 1 e '+total+', em ordem crescente.');
    if(end-start>=100)throw Error('Importe até 100 páginas por vez.');
    for(let n=start;n<=end;n++)values.push(n);
   }
  }else throw Error('Escolha quais páginas importar.');
  values=[...new Set(values)].sort((a,b)=>a-b);
  if(!values.length||values.some(v=>!Number.isInteger(v)||v<1||v>total))throw Error('Escolha páginas entre 1 e '+total+'.');
  if(values.length>100)throw Error('Importe até 100 páginas por vez.');
  return values;
 }
 function fromBook(book){
  if(Array.isArray(book.croqui_pages))return book.croqui_pages;
  return book.croqui||book.drawing?[{id:id(),croqui:book.croqui||null,drawing:book.drawing||null}]:[];
 }
 function page(ref,source,pdf={}){
  return {id:id(),croqui:{...ref,caption:''},drawing:{version:1,width:1200,height:800,objects:[],background_ref:ref.ref,background_source:source,pdf_text_background_ref:pdf.cleanRef||null,pdf_texts:pdf.texts||[],pdf_source_ref:pdf.pdfRef||null,pdf_lines:pdf.lines||[]}};
 }
 window.CroquiPages={selection,fromBook,page,id};
})();
