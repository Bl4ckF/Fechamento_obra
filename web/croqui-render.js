'use strict';
// Exporta em segundo plano quando OffscreenCanvas está disponível.
(() => {
 let worker=null,sequence=0;const pending=new Map();
 function workerFor(){
  if(worker)return worker;
  worker=new Worker('/croqui-render-worker.js');
  worker.onmessage=event=>{const {id,blob,error}=event.data,request=pending.get(id);if(!request)return;pending.delete(id);error?request.reject(Error(error)):request.resolve(blob);};
  worker.onerror=()=>{for(const request of pending.values())request.reject(Error('Não foi possível preparar o croqui em segundo plano.'));pending.clear();worker.terminate();worker=null;};
  return worker;
 }
 function dataURL(blob){if(blob.size>32000000)throw Error('O croqui ultrapassa 32 MB em PNG.');return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(Error('Não foi possível ler a imagem do croqui.'));reader.readAsDataURL(blob);});}
 async function png(doc,pictures){
  // O fundo já contém os traços e textos não alterados. Não transfira milhares
  // de geometrias originais ao worker para redesenhar apenas as edições.
  const editedText=new Set(doc.objects.map(o=>o.pdf_text_id).filter(Boolean));
  const {pdf_lines,...page}=doc;doc={...page,pdf_texts:(doc.pdf_texts||[]).filter(t=>editedText.has(t.id))};
  const size=window.CroquiQuality.exportSize(pictures.original);
  if(typeof Worker!=='undefined'&&typeof OffscreenCanvas!=='undefined'&&typeof createImageBitmap==='function'){
   let original,clean;
   try{
    original=pictures.original?await createImageBitmap(pictures.original):null;clean=pictures.clean?await createImageBitmap(pictures.clean):null;
    const id=++sequence,w=workerFor(),blob=await new Promise((resolve,reject)=>{pending.set(id,{resolve,reject});try{w.postMessage({id,doc,size,catalog:window.NetworkSymbols.all(),original,clean},[original,clean].filter(Boolean));}catch(error){pending.delete(id);reject(error);}});
    return await dataURL(blob);
   }catch(error){original?.close();clean?.close();/* Navegadores sem suporte completo usam toBlob abaixo. */}
  }
  const canvas=document.createElement('canvas');canvas.width=size.width;canvas.height=size.height;const context=canvas.getContext('2d');context.scale(size.width/1200,size.height/800);context.imageSmoothingQuality='high';window.Drawing.render(context,doc,'',false,pictures);
  if(!canvas.toBlob)return window.CroquiQuality.pngData(canvas);
  const blob=await new Promise((resolve,reject)=>canvas.toBlob(value=>value?resolve(value):reject(Error('Não foi possível preparar a imagem do croqui.')),'image/png'));return dataURL(blob);
 }
 window.CroquiRender={png};
})();
