'use strict';
// PDF independente do book. Todas as dependências e imagens são locais.
(() => {
 async function build(pages,{title='Croqui editado',progress=()=>{},read}={}){
  if(!pages?.length)throw Error('Importe o croqui antes de salvar o PDF.');
  const pdf=await window.PDFLib.PDFDocument.create();pdf.setTitle(title);pdf.setCreator('Fechamento de Obras Engelmig');
  const get=read|| (async ref=>{const response=await fetch('/media/'+encodeURIComponent(ref));if(!response.ok)throw Error('Não foi possível ler uma página do croqui.');return new Uint8Array(await response.arrayBuffer());});
  for(let i=0;i<pages.length;i++){
   const item=pages[i];if(!item.croqui?.ref)throw Error('Aguarde o salvamento da página '+(i+1)+'.');
   progress(i+1,pages.length);let bytes=await get(item.croqui.ref),image;
   if(/\.png$/i.test(item.croqui.ref))image=await pdf.embedPng(bytes);
   else if(/\.jpe?g$/i.test(item.croqui.ref))image=await pdf.embedJpg(bytes);
   else{const bitmap=await createImageBitmap(new Blob([bytes]));try{const canvas=document.createElement('canvas');canvas.width=bitmap.width;canvas.height=bitmap.height;canvas.getContext('2d').drawImage(bitmap,0,0);image=await pdf.embedPng(window.CroquiQuality.pngData(canvas));}finally{bitmap.close();}}
   const source=item.drawing?.background_source||{},width=source.page_width||841.89,height=source.page_height||561.26,page=pdf.addPage([width,height]),scale=Math.min(width/image.width,height/image.height);
   page.drawImage(image,{x:(width-image.width*scale)/2,y:(height-image.height*scale)/2,width:image.width*scale,height:image.height*scale});
   // Libera os pixels descompactados de cada imagem antes da próxima página.
   await pdf.flush();bytes=null;
  }
  return pdf.save();
 }
 async function download(pages,workOrder,progress){
  const name='Croqui_'+(String(workOrder||'obra').replace(/[^\p{L}\p{N}_-]/gu,'_').slice(0,80)||'obra')+'_editado.pdf',bytes=await build(pages,{title:'Croqui editado · '+(workOrder||'Obra'),progress});
  const url=URL.createObjectURL(new Blob([bytes],{type:'application/pdf'})),link=document.createElement('a');link.href=url;link.download=name;document.body.appendChild(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),30000);return name;
 }
 window.CroquiExport={build,download};
})();
