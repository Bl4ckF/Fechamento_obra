'use strict';
(()=>{
 const link=document.createElement('link');link.rel='stylesheet';link.href='/operations-shell.css';document.head.append(link);
 const supported=new Set(['cadcraft','pdfcraft','photocraft']);
 const workspace=document.createElement('section');workspace.id='operationsWorkspace';workspace.hidden=true;
 workspace.innerHTML='<header><strong id="operationTitle">Operação</strong><button type="button" id="returnToWork">Minimizar editor</button></header><p id="operationNotice" role="status"></p><div id="operationFrames"></div>';
 const frames=new Map(),dirty=new Set(),contexts=new Map(),ready=new Set(),saving=new Set(),saveErrors=new Set(),saveQueues=new Map(),dirtyVersions=new Map();let catalog=[],activeOperation='';
 const savedList=document.createElement('div');savedList.id='operationSavedFiles';workspace.insertBefore(savedList,workspace.querySelector('#operationFrames'));
 const encode=bytes=>{let value='';const array=new Uint8Array(bytes);for(let i=0;i<array.length;i+=16384)value+=String.fromCharCode(...array.subarray(i,i+16384));return btoa(value);};
 const decode=data=>Uint8Array.from(atob(data),character=>character.charCodeAt(0)).buffer;
 async function refreshDocuments(id){
  if(id!==activeOperation)return;
  savedList.replaceChildren();const context=contexts.get(id);const records=await api('/api/operation-documents?context='+encodeURIComponent(context)+'&operation='+encodeURIComponent(id));
  if(id!==activeOperation||context!==contexts.get(id))return;
  records.filter(item=>item.operation===id&&item.context===context).forEach(item=>{
   const button=document.createElement('button');button.textContent='Reabrir: '+item.name;button.onclick=()=>{if(!ready.has(id))return;const bytes=decode(item.data);frames.get(id).contentWindow.postMessage({type:id+':open',name:item.name,bytes},location.origin,[bytes]);};savedList.append(button);
   if(/\.(pdf|png|jpe?g|webp)$/i.test(item.name)){
    const apply=document.createElement('button');apply.textContent='Usar '+item.name+' no croqui';apply.onclick=async()=>{
     try{if(context!==S.draftId)throw Error('Este documento pertence a outro rascunho. Reabra a obra de origem.');
      if(!confirm('Substituir as páginas atuais do croqui por este documento?'))return;
      const extension=item.name.split('.').pop().toLowerCase(),type={pdf:'application/pdf',png:'image/png',jpg:'image/jpeg',jpeg:'image/jpeg',webp:'image/webp'}[extension];
      await window.Book.attachCroqui(new File([decode(item.data)],item.name,{type}));workspace.hidden=true;showTab('conductors');
     }catch(error){document.getElementById('operationNotice').textContent=error.message;}
    };savedList.append(apply);
   }
  });
 }
 workspace.querySelector('#returnToWork').onclick=()=>{workspace.hidden=true;document.querySelector('[data-editor-open="'+activeOperation+'"]')?.focus();};
 async function open(id){
  if(!supported.has(id))return;
  showTab('conductors');
  const operation=catalog.find(item=>item.id===id);if(!operation)return;
  activeOperation=id;
  await window.Drawing?.flush();await window.Training?.flush();
  workspace.hidden=false;document.getElementById('operationTitle').textContent=operation.name;
  const notice=document.getElementById('operationNotice');
  if(!operation.available){notice.textContent='Esta operação ainda não está disponível nesta instalação.';frames.forEach(frame=>frame.hidden=true);savedList.replaceChildren();return;}
  notice.textContent='Carregando a operação…';
  if(frames.has(id)&&contexts.get(id)!==S.draftId){
   if(dirty.has(id)||saving.has(id)||saveErrors.has(id))throw Error('Salve o documento da obra anterior antes de trocar de obra nesta operação.');
   frames.get(id).remove();frames.delete(id);contexts.delete(id);ready.delete(id);
  }
  if(!frames.has(id)){
   const frame=document.createElement('iframe');frame.title=operation.name+' — operação integrada';frame.src=operation.url;frame.dataset.operation=id;
   document.getElementById('operationFrames').append(frame);frames.set(id,frame);contexts.set(id,typeof S!=='undefined'?S.draftId:'');
  }
  frames.forEach((frame,key)=>frame.hidden=key!==id);if(ready.has(id))notice.textContent='';await refreshDocuments(id);
 }
 window.addEventListener('message',async event=>{
  if(event.origin!==location.origin)return;
  const entry=[...frames].find(([,frame])=>frame.contentWindow===event.source);if(!entry)return;
  const [id]=entry;const message=event.data;if(!message||typeof message.type!=='string'||!message.type.startsWith(id+':'))return;
  if(message.type===id+':dirty'){if(message.dirty){dirty.add(id);dirtyVersions.set(id,(dirtyVersions.get(id)||0)+1);}else if(!saving.has(id)&&!saveErrors.has(id))dirty.delete(id);}
  if(message.type===id+':ready'){
   ready.add(id);frames.get(id).dataset.ready='true';document.getElementById('operationNotice').textContent='';
   if(id==='pdfcraft'){
    try{await window.Book.flushCroquis();const pages=structuredClone(window.Book.summary().croqui_pages||[]);
     if(pages.length&&contexts.get(id)===S.draftId){const bytes=await window.CroquiExport.build(pages);const buffer=bytes.slice().buffer;event.source.postMessage({type:'pdfcraft:open',name:'Croqui.pdf',bytes:buffer},location.origin,[buffer]);}
    }catch(error){document.getElementById('operationNotice').textContent='Não foi possível carregar o croqui: '+error.message;}
   }
  }
  if(message.type===id+':failed')document.getElementById('operationNotice').textContent=String(message.error||'Falha ao iniciar a operação.');
  if(message.type===id+':open-pending')document.getElementById('operationNotice').textContent='Documento interno preparado. Use Arquivo → Abrir na operação para carregá-lo.';
  if(message.type===id+':save'){
   dirty.add(id);saving.add(id);
   const version=dirtyVersions.get(id)||0,capturedContext=contexts.get(id);
   const previous=saveQueues.get(id)||Promise.resolve();
   const work=previous.then(async()=>{
   try{
    const bytes=message.bytes instanceof ArrayBuffer?message.bytes:message.bytes instanceof Uint8Array?message.bytes.slice().buffer:null;
    if(!bytes||bytes.byteLength>50_000_000)throw Error('Arquivo inválido ou maior que 50 MB.');
    const name=String(message.name||'documento').slice(0,240);const context=capturedContext;
    await api('/api/operation-documents',{context,operation:id,name,data:encode(bytes)});
    if(version===(dirtyVersions.get(id)||0)&&saveQueues.get(id)===work)dirty.delete(id);saveErrors.delete(id);document.getElementById('operationNotice').textContent='Documento salvo no fechamento e incluído no backup da obra.';await refreshDocuments(id);
   }catch(error){saveErrors.add(id);document.getElementById('operationNotice').textContent='Não foi possível salvar: '+error.message+' Mantenha o editor aberto.';}finally{if(saveQueues.get(id)===work)saving.delete(id);}
   });saveQueues.set(id,work);await work;
  }
 });
 window.addEventListener('beforeunload',event=>{if(dirty.size||saving.size||saveErrors.size){event.preventDefault();event.returnValue='';}});
 function renderEditors(){
  const buttons=document.getElementById('editingProgramButtons');if(!buttons)return;
  buttons.replaceChildren();
  for(const [id,name,description] of [['cadcraft','CADCraft','Desenho técnico e projetos'],['pdfcraft','PDFCraft','Edição de documentos PDF'],['photocraft','PhotoCraft','Edição de fotos e imagens']]){
   const operation=catalog.find(item=>item.id===id),card=document.createElement('article');card.className='editing-program';
   const title=document.createElement('h3');title.textContent=name;
   const detail=document.createElement('p');detail.textContent=description;
   const button=document.createElement('button');button.type='button';button.className='primary';button.dataset.editorOpen=id;
   button.textContent=operation?.available?'Abrir '+name:name+' · em preparação';button.disabled=!operation?.available;
   button.onclick=()=>open(id).catch(error=>{document.getElementById('operationNotice').textContent=error.message;});
   card.append(title,detail,button);buttons.append(card);
  }
  const available=catalog.filter(item=>item.available).length;
  document.getElementById('editingProgramStatus').textContent=available===3?'Os três editores estão disponíveis dentro do Fechamento.':available+' de 3 editores disponíveis nesta instalação.';
 }
 function installEditors(){
  const tab=document.getElementById('tab-conductors');if(!tab||document.getElementById('editingPrograms'))return;
  const section=document.createElement('section');section.id='editingPrograms';section.className='card editing-programs';
  section.innerHTML='<div class="section-heading"><div><h2>Editores integrados</h2><p>Abra projetos, PDFs e fotos sem sair do Fechamento.</p></div><button type="button" class="secondary" id="refreshEditingPrograms">Atualizar editores</button></div><div id="editingProgramButtons"></div><p id="editingProgramStatus" class="muted" role="status"></p>';
  tab.querySelector('.page-heading').after(section);section.append(workspace);
  document.getElementById('refreshEditingPrograms').onclick=()=>loadCatalog().catch(error=>{document.getElementById('editingProgramStatus').textContent=error.message;});
  renderEditors();
 }
 async function loadCatalog(){
  const response=await fetch('/api/programs');if(!response.ok)throw Error('Não foi possível carregar os editores.');const payload=await response.json();
  catalog=(payload.programs||[]).filter(item=>supported.has(item.id));installEditors();renderEditors();
 }
 installEditors();loadCatalog().catch(error=>{const status=document.getElementById('editingProgramStatus');if(status)status.textContent=error.message;});
 const observer=new MutationObserver(installEditors);observer.observe(document.querySelector('main'),{childList:true,subtree:true});
 window.IntegratedOperations={open};
})();
