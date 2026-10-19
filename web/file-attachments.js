'use strict';
(() => {
 let queue=Promise.resolve(),highlighted=null,dragDepth=0;
 const mime=file=>/\.pdf$/i.test(file.name||'')?'application/pdf':file.type||({'png':'image/png','jpg':'image/jpeg','jpeg':'image/jpeg','webp':'image/webp','gif':'image/gif','bmp':'image/bmp','avif':'image/avif'}[(file.name||'').split('.').pop().toLowerCase()]||'');
 function filesFrom(data){const files=Array.from(data?.files||[]);return files.length?files:Array.from(data?.items||[]).filter(item=>item.kind==='file').map(item=>item.getAsFile()).filter(Boolean);}
 function isFileDrag(event){return Array.from(event.dataTransfer?.types||[]).includes('Files');}
 function clearHighlight(){highlighted?.classList.remove('attachment-dragging');highlighted=null;dragDepth=0;}
 function destination(event){
  const target=event.target?.closest?.('[data-attachment-target]');if(target&&!target.closest('.tab')?.hidden)return target.dataset.attachmentTarget;
  if(!$('tab-book')?.hidden)return 'photos';if(!$('tab-conductors')?.hidden)return 'croqui';return '';
 }
 function highlight(kind){const zone=document.querySelector(`[data-attachment-target="${kind}"]`);if(zone===highlighted)return;highlighted?.classList.remove('attachment-dragging');highlighted=zone;zone?.classList.add('attachment-dragging');}
 function add(kind,input){
  const files=Array.from(input||[]);if(!files.length)return Promise.resolve();
  const owner=window.Book.summary(),pointId=window.Book.activeId();
  const task=queue.catch(()=>{}).then(async()=>{
   if(window.Book.summary()!==owner)throw Error('A obra mudou antes do anexo. Selecione os arquivos novamente na obra desejada.');
   if(kind==='photos'&&!owner.points.some(p=>p.id===pointId))throw Error('Cadastre ou selecione um ponto antes de anexar as fotos.');
   if(!['photos','croqui'].includes(kind))throw Error('Abra Pontos e serviços ou Croqui para anexar os arquivos.');
   const accepted=files.filter(file=>mime(file).startsWith('image/')||(kind==='croqui'&&mime(file)==='application/pdf'));
   if(accepted.length!==files.length)throw Error(kind==='photos'?'Anexe apenas imagens nas fotos do ponto. PDFs e projetos devem ir para o croqui.':'No croqui, anexe imagens ou um arquivo PDF.');
   if(kind==='croqui'&&accepted.length>1&&accepted.some(file=>mime(file)==='application/pdf'))throw Error('Anexe um PDF por vez. Você pode selecionar várias páginas dentro dele ou anexar várias imagens juntas.');
   const prepared=accepted.map(file=>file.type?file:new File([file],file.name||'Imagem_colada.png',{type:mime(file),lastModified:file.lastModified||Date.now()}));
   if(kind==='photos')return window.Book.attachPhotos(prepared,pointId);
   return window.Book.attachCroqui(prepared.length===1?prepared[0]:prepared);
  });queue=task;return task;
 }
 document.addEventListener('paste',event=>{
  const files=filesFrom(event.clipboardData);if(!files.length||event.defaultPrevented||document.querySelector('dialog[open]'))return;
  const kind=destination(event);if(!kind)return;event.preventDefault();event.stopPropagation();add(kind,files).catch(error=>toast(error.message,true));
 },true);
 document.addEventListener('dragenter',event=>{if(!isFileDrag(event))return;event.preventDefault();dragDepth++;if(!document.querySelector('dialog[open]'))highlight(destination(event));});
 document.addEventListener('dragover',event=>{if(!isFileDrag(event))return;event.preventDefault();event.dataTransfer.dropEffect='copy';if(!document.querySelector('dialog[open]'))highlight(destination(event));});
 document.addEventListener('dragleave',event=>{if(!isFileDrag(event))return;if(--dragDepth<=0)clearHighlight();});
 document.addEventListener('drop',event=>{
  const files=filesFrom(event.dataTransfer);if(!files.length)return;const kind=destination(event);event.preventDefault();event.stopPropagation();clearHighlight();
  if(document.querySelector('dialog[open]')){toast('Conclua ou cancele a janela aberta antes de anexar outro arquivo.',true);return;}
  add(kind,files).catch(error=>toast(error.message,true));
 });
 window.addEventListener('blur',clearHighlight);window.FileAttachments={add,filesFrom};
})();
