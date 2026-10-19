'use strict';
// Importação local, página por página, sem acumular os bitmaps do PDF na memória.
(() => {
 let library=null,loading=null,documentPDF=null,result=null,renderTask=null,sequence=0,session=0,rotation=0,filename='',passwordCallback=null,prepared=null,protectedPDF=false,importing=false,acceptPage=null;
 document.body.insertAdjacentHTML('beforeend',`<dialog id="pdfBackgroundDialog" class="pdf-background-dialog"><div class="dialog-heading"><div><h2>Importar páginas do PDF</h2><p id="pdfBackgroundName"></p></div><button id="pdfBackgroundCancel" class="secondary">Cancelar</button></div>
 <div class="actions"><label>Importar<select id="pdfScope"><option value="single">Uma página específica</option><option value="all">Todas as páginas</option><option value="range">Intervalo / lista de páginas</option></select></label><label id="pdfRangeLabel" hidden>Páginas<input id="pdfRange" placeholder="Ex.: 2-5 ou 1,3,7-9" maxlength="600"></label></div>
 <div class="actions section-spacer"><button id="pdfPrevious" class="secondary">Anterior</button><label>Página da prévia<input id="pdfPage" type="number" min="1" value="1" aria-label="Página específica / prévia"></label><span id="pdfPageCount"></span><button id="pdfNext" class="secondary">Próxima</button><button id="pdfRotate" class="secondary">Girar seleção 90°</button></div>
 <div id="pdfPasswordBox" hidden><label>Senha deste PDF<input id="pdfPassword" type="password" autocomplete="off"></label><button id="pdfUnlock" class="secondary">Abrir PDF</button></div><p id="pdfBackgroundStatus" role="status"></p><div class="pdf-page-preview"><canvas id="pdfPageCanvas" aria-label="Prévia do croqui"></canvas></div><div class="actions section-spacer"><button id="pdfBackgroundUse" class="primary" disabled>Importar seleção</button></div><p class="muted">Até 100 páginas por importação. A seleção substitui o croqui atual. Depois, use Anterior / Próxima para editar cada página e Salvar PDF editado para baixar um documento separado. A rotação escolhida vale para toda a seleção.</p><p class="muted">Textos e traços vetoriais reconhecidos ficam selecionáveis. PDFs escaneados permitem sobrepor símbolos e linhas; não há OCR nesta versão.</p></dialog>`);
 const node=id=>document.getElementById(id),dialog=node('pdfBackgroundDialog');
 async function lib(){if(!library){library=await import('/vendor/pdfjs/pdf.min.mjs');library.GlobalWorkerOptions.workerSrc='/vendor/pdfjs/pdf.worker.min.mjs';}return library;}
 const controls=['pdfPage','pdfPrevious','pdfNext','pdfRotate','pdfScope','pdfRange'];
 function lock(value){importing=value;for(const name of controls)node(name).disabled=value;node('pdfBackgroundUse').disabled=value||!prepared;}
 async function cleanup(){sequence++;session++;prepared=null;renderTask?.cancel();renderTask=null;passwordCallback=null;node('pdfPassword').value='';if(loading){const task=loading;loading=null;await task.destroy();}documentPDF=null;importing=false;}
 async function finish(value){const done=result;result=null;dialog.close();await cleanup();done?.(value);}
 async function renderPage(number=Number(node('pdfPage').value),batch=false){
  if(!documentPDF)return false;
  const seq=++sequence;prepared=null;const previous=renderTask;previous?.cancel();renderTask=null;node('pdfBackgroundUse').disabled=true;
  number=Math.max(1,Math.min(documentPDF.numPages,Math.trunc(number)||1));node('pdfPage').value=number;
  node('pdfPrevious').disabled=batch||number===1;node('pdfNext').disabled=batch||number===documentPDF.numPages;
  node('pdfBackgroundStatus').textContent='Preparando página '+number+'…';
  try{
   if(previous)await previous.promise.catch(()=>{});
   const page=await documentPDF.getPage(number);if(seq!==sequence)return false;
   const initial=page.getViewport({scale:1,rotation:(page.rotate+rotation)%360}),size=window.CroquiQuality.sourceSize(initial.width,initial.height,true),viewport=page.getViewport({scale:size.scale,rotation:(page.rotate+rotation)%360});
   const operators=await page.getOperatorList();if(seq!==sequence)return false;
   const lines=protectedPDF?[]:window.PDFLines.extract(operators,viewport,library,size.width,size.height);
   const canvas=document.createElement('canvas');canvas.id='pdfPageCanvas';canvas.setAttribute('aria-label','Prévia da página '+number);canvas.width=size.width;canvas.height=size.height;
   node('pdfPageCanvas').replaceWith(canvas);renderTask=page.render({canvasContext:canvas.getContext('2d'),viewport,background:'#ffffff'});await renderTask.promise;if(seq!==sequence)return false;renderTask=null;
   const content=await page.getTextContent();if(seq!==sequence)return false;
   const texts=window.PDFText.mapText(content,viewport,library,canvas.width,canvas.height);if(texts.length>3000)throw Error('Mais de 3.000 blocos de texto nesta página. Divida o projeto antes de importar.');
   let cleanCanvas=null;
   if(texts.length){cleanCanvas=document.createElement('canvas');cleanCanvas.width=canvas.width;cleanCanvas.height=canvas.height;renderTask=page.render({canvasContext:cleanCanvas.getContext('2d'),viewport,background:'#ffffff',operationsFilter:window.PDFText.textFilter(library)});await renderTask.promise;if(seq!==sequence)return false;renderTask=null;}
   prepared={texts,lines,cleanCanvas,source:{kind:'pdf',name:filename,page:number,rotation,page_width:initial.width,page_height:initial.height}};
   node('pdfBackgroundStatus').textContent=texts.length+' textos e '+lines.length+' traços vetoriais reconhecidos na página '+number+'. '+(protectedPDF?'Para editar linhas do original, importe uma cópia do PDF sem senha.':'');node('pdfBackgroundUse').disabled=batch;return true;
  }catch(error){if(seq!==sequence||error.name==='RenderingCancelledException')return false;node('pdfBackgroundStatus').textContent='Não foi possível preparar a página '+number+': '+error.message;return false;}
 }
 async function choose(file,onPage){
  if(file.size>50*1024*1024)throw Error('Use um PDF de até 50 MB.');if(typeof onPage!=='function')throw Error('Atualize os arquivos do editor de PDF.');
  await cleanup();acceptPage=onPage;protectedPDF=false;filename=file.name;rotation=0;node('pdfBackgroundName').textContent=filename;node('pdfPage').value=1;node('pdfScope').value='single';node('pdfRange').value='';node('pdfRangeLabel').hidden=true;node('pdfPageCount').textContent='';node('pdfPasswordBox').hidden=true;node('pdfBackgroundStatus').textContent='Abrindo PDF…';node('pdfPageCanvas').width=1;node('pdfPageCanvas').height=1;lock(false);
  dialog.showModal();const answer=new Promise(resolve=>{result=resolve;}),ticket=session;
  try{
   const pdf=await lib(),data=new Uint8Array(await file.arrayBuffer());if(ticket!==session)return answer;
   loading=pdf.getDocument({data,isEvalSupported:false,stopAtErrors:true,maxImageSize:24000000,cMapUrl:'/vendor/pdfjs/cmaps/',cMapPacked:true,standardFontDataUrl:'/vendor/pdfjs/standard_fonts/',wasmUrl:'/vendor/pdfjs/wasm/'});
   loading.onPassword=callback=>{protectedPDF=true;passwordCallback=callback;node('pdfPasswordBox').hidden=false;node('pdfBackgroundStatus').textContent='Informe a senha para abrir este PDF.';node('pdfPassword').focus();};
   const doc=await loading.promise;if(ticket!==session)return answer;documentPDF=doc;node('pdfPasswordBox').hidden=true;node('pdfPassword').value='';node('pdfPageCount').textContent='de '+doc.numPages;node('pdfPage').max=doc.numPages;await renderPage(1);
  }catch(error){if(ticket===session)node('pdfBackgroundStatus').textContent='Não foi possível abrir este PDF: '+error.message;}
  return answer;
 }
 node('pdfBackgroundCancel').onclick=()=>finish(null);dialog.addEventListener('cancel',event=>{event.preventDefault();finish(null);});
 node('pdfScope').onchange=()=>{node('pdfRangeLabel').hidden=node('pdfScope').value!=='range';};
 node('pdfPrevious').onclick=()=>renderPage(Number(node('pdfPage').value)-1);node('pdfNext').onclick=()=>renderPage(Number(node('pdfPage').value)+1);node('pdfPage').onchange=()=>renderPage();node('pdfRotate').onclick=()=>{rotation=(rotation+90)%360;renderPage();};
 node('pdfUnlock').onclick=()=>{passwordCallback?.(node('pdfPassword').value);node('pdfPassword').value='';};
 node('pdfBackgroundUse').onclick=async()=>{
  if(importing||!prepared)return;const ticket=session;
  try{
   const numbers=window.CroquiPages.selection(node('pdfScope').value,node('pdfRange').value,documentPDF.numPages,Number(node('pdfPage').value)),pages=[];lock(true);
   for(let i=0;i<numbers.length;i++){
    if(ticket!==session)return;
    if(prepared?.source.page!==numbers[i]&&!(await renderPage(numbers[i],true))){if(ticket!==session)return;throw Error(node('pdfBackgroundStatus').textContent);}
    if(ticket!==session)return;node('pdfBackgroundStatus').textContent='Salvando página '+numbers[i]+' ('+(i+1)+' de '+numbers.length+')…';
    const item=prepared,canvas=node('pdfPageCanvas');
    const saved=await acceptPage({data:window.CroquiQuality.pngData(canvas),cleanData:item.cleanCanvas?window.CroquiQuality.pngData(item.cleanCanvas):null,texts:item.texts,lines:item.lines,name:filename+' — página '+numbers[i],source:item.source});
    if(ticket!==session)return;pages.push(saved);prepared=null;
   }
   await finish({pages});
  }catch(error){if(ticket===session){const message=error.message;lock(false);if(!prepared)await renderPage();if(ticket===session)node('pdfBackgroundStatus').textContent=message;}}
 };
 window.CroquiPDF={choose};
})();
