'use strict';
// Re-renderiza o PDF original omitindo somente os traços que foram editados.
(() => {
 let library,cache,queue=Promise.resolve(),task,activePreview=false,previewRevision=0;const rendered=new Map();
 async function lib(){if(!library){library=await import('/vendor/pdfjs/pdf.min.mjs');library.GlobalWorkerOptions.workerSrc='/vendor/pdfjs/pdf.worker.min.mjs';}return library;}
 async function documentFor(ref){
  if(cache?.ref===ref)return cache.promise;
  if(cache)await cache.loading.destroy();
  const pdf=await lib(),loading=pdf.getDocument({url:'/media/'+encodeURIComponent(ref),isEvalSupported:false,stopAtErrors:true,maxImageSize:24000000,cMapUrl:'/vendor/pdfjs/cmaps/',cMapPacked:true,standardFontDataUrl:'/vendor/pdfjs/standard_fonts/',wasmUrl:'/vendor/pdfjs/wasm/'});
  cache={ref,loading,promise:loading.promise};
  try{return await cache.promise;}catch(error){cache=null;throw error;}
 }
 function render(ref,source,excluded,withText,preview=false){
  const key=JSON.stringify([ref,source,excluded,withText,preview]),slot=preview?'preview':'full';if(rendered.get(slot)?.key===key)return rendered.get(slot).promise;
  const revision=preview?++previewRevision:0;
  if(preview&&activePreview){activePreview=false;task?.cancel();}
  const check=()=>{if(preview&&revision!==previewRevision){const error=Error('Prévia substituída pela edição mais recente.');error.name='RenderingCancelledException';throw error;}};
  const run=async()=>{
   check();
   const pdf=await lib(),doc=await documentFor(ref),page=await doc.getPage(source.page||1),rotation=(page.rotate+(source.rotation||0))%360,initial=page.getViewport({scale:1,rotation}),size=window.CroquiQuality.sourceSize(initial.width,initial.height,true),factor=preview?Math.min(1,1800/Math.max(size.width,size.height)):1,viewport=page.getViewport({scale:size.scale*factor,rotation}),hidden=new Set(excluded),textFilter=window.PDFText.textFilter(pdf);
   const paint=async(noText)=>{check();const canvas=document.createElement('canvas');canvas.width=Math.max(1,Math.floor(size.width*factor));canvas.height=Math.max(1,Math.floor(size.height*factor));
    activePreview=preview;task=page.render({canvasContext:canvas.getContext('2d'),viewport,background:'#ffffff',operationsFilter:(index,ops)=>!hidden.has(index)&&(!noText||textFilter(index,ops))});
    try{await task.promise;check();return canvas;}catch(error){canvas.width=canvas.height=1;throw error;}finally{task=null;activePreview=false;}
   };
   const original=await paint(false),clean=withText?await paint(true):null;return {original,clean};
  };
  const answer=queue.then(run,run);queue=answer.catch(()=>{});rendered.set(slot,{key,promise:answer});answer.catch(()=>{if(rendered.get(slot)?.key===key)rendered.delete(slot);});return answer;
 }
 window.PDFSource={render};
})();
