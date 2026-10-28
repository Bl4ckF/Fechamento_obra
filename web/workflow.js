'use strict';
// Organização da operação e prévia de leitura, sem criar registros de obra.
(() => {
 const stages=[['work','Dados da obra','Número, data, responsável e local'],['book','Pontos e serviços','Fotos, serviços, materiais e condutores'],['conductors','Edição','CADCraft, PDFCraft e PhotoCraft'],['forms','Revisão e envio','Conferência, PDFs e Forms']];
 let current='work',ready=false,timer,revision=0,running=false,page=0,pages=0,lastHTML='',pinned=false,popup=null;
 const stageButton=(s,i)=>`<button class="stage-link" data-stage="${s[0]}"><span class="stage-number">${i+1}</span><span><strong>${s[1]}</strong><small>${s[2]}</small><em data-stage-state="${s[0]}">A preencher</em></span></button>`;
 function install(){
  const main=document.querySelector('main');
  main.insertAdjacentHTML('afterbegin',`<nav id="operationStages" class="operation-stages" aria-label="Etapas do fechamento">${stages.map(stageButton).join('')}</nav>`);
  if($('automaticStatus'))$('operationStages').before($('automaticStatus'));
  for(const [i,s] of stages.entries()){
   const nav=document.querySelector(`.nav[data-tab="${s[0]}"]`);nav.innerHTML=`<span>0${i+1}</span> ${s[1]}`;
   const tab=$('tab-'+s[0]);tab.insertAdjacentHTML('beforeend',`<div class="stage-footer"><span>Etapa ${i+1} de 4 · Alterações salvas automaticamente</span><div class="actions">${i?`<button class="secondary" data-stage="${stages[i-1][0]}">← ${stages[i-1][1]}</button>`:''}${i<3?`<button class="primary" data-next-stage="${s[0]}" data-destination="${stages[i+1][0]}">Continuar: ${stages[i+1][1]} →</button>`:''}</div></div>`);
  }
  const navigation=document.querySelector('nav[aria-label="Menu principal"]');
  const secondary=document.createElement('details');secondary.id='secondaryNavigation';secondary.className='secondary-navigation';
  secondary.innerHTML='<summary>Outras opções</summary><div id="secondaryNavigationItems"></div>';
  const mainTabs=new Set(stages.map(stage=>stage[0]));
  navigation.querySelectorAll('.nav').forEach(button=>{if(!mainTabs.has(button.dataset.tab))secondary.lastElementChild.append(button);});
  navigation.append(secondary);
  try{secondary.open=localStorage.getItem('engelmig-secondary-navigation-open')==='true';}catch{}
  secondary.addEventListener('toggle',()=>{try{localStorage.setItem('engelmig-secondary-navigation-open',String(secondary.open));}catch{}});
  document.querySelector('#tab-work h1').textContent='Vamos identificar a obra';
  document.querySelector('#tab-work .page-heading p:not(.eyebrow)').textContent='Comece pelos dados que vão identificar o book e os registros da equipe.';
  const metadata=document.querySelector('.metadata');
  metadata.insertAdjacentHTML('beforebegin','<div class="stage-title"><span class="step">1</span><div><h2>Dados da obra</h2><p>Preencha os quatro campos para continuar.</p></div></div>');
  for(const id of ['workOrder','date','responsible','location'])$(id).required=true;
  metadata.insertAdjacentHTML('afterend','<div class="start-guide"><strong>Depois, trabalhe ponto a ponto.</strong><p>Adicione a foto de referência, escolha os serviços e confira os materiais ao lado dela. O book acompanha os lançamentos automaticamente.</p></div>');
  const conductorPanel=$('pointConductors'),conductorFold=document.createElement('details');conductorFold.className='card conductor-fold';conductorFold.innerHTML='<summary>Trechos de condutores · abrir para preencher</summary>';$('tab-book').querySelector('.stage-footer').before(conductorFold);conductorFold.append(conductorPanel);
  document.querySelector('#tab-conductors h1').textContent='Edição';
  document.querySelector('#tab-conductors .page-heading p:not(.eyebrow)').textContent='Edite projetos, PDFs e fotos dentro do Fechamento com CADCraft, PDFCraft e PhotoCraft.';
  const attachment=document.querySelector('#tab-conductors [data-attachment-target="croqui"]');
  const attachmentFold=document.createElement('details');attachmentFold.className='editing-attachment';
  attachmentFold.innerHTML='<summary>Croqui do book · importar e conferir</summary>';attachment.before(attachmentFold);attachmentFold.append(attachment);
  const workspace=$('pointServices');workspace.append(document.querySelector('.workflow'),document.querySelector('.work-items'));
  const bookHeading=document.querySelector('#tab-book .page-heading');
  bookHeading.querySelector('h1').textContent='Pontos e serviços';
  bookHeading.querySelector('p:not(.eyebrow)').textContent='Use a foto como referência para lançar os serviços do ponto.';
  bookHeading.insertAdjacentHTML('afterend',`<div id="pointStageActions" class="point-stage-actions"><div class="actions" role="group" aria-label="Ações da mão de obra selecionada"><button id="clearEditorChanges" class="secondary" disabled>Limpar alterações</button><button id="removeSelectedLabor" class="secondary remove-selected-labor" disabled>Remover mão de obra selecionada</button></div><div class="actions" id="pointViewActions"><details class="point-more-actions"><summary>Mais opções</summary><div id="pointMoreActions"></div></details></div></div>`);
  $('pointViewActions').prepend($('previewBook'));
  $('pointMoreActions').append($('previewMaterials'),$('clearDraft'));
  bookHeading.querySelector('.actions').remove();
  $('clearEditorChanges').onclick=run(()=>editorAction(clearEditorChanges));
  $('removeSelectedLabor').onclick=run(()=>editorAction(removeSelectedLabor));
  const finder=document.createElement('details');finder.id='laborFinder';finder.className='card labor-finder';finder.open=true;
  const labor=document.querySelector('.labor-panel');labor.before(finder);finder.innerHTML='<summary>Buscar e adicionar mão de obra <span>nome ou código</span></summary>';finder.append(labor);
  $('laborSearch').placeholder='Digite o nome ou código da mão de obra…';
  $('laborSearch').setAttribute('aria-label','Buscar mão de obra pelo nome ou código');
  labor.querySelector('h2').textContent='Escolha a mão de obra';
  document.querySelector('.detail-panel h2').textContent='Mão de obra e materiais do ponto';
  document.querySelector('.work-items h2').textContent='Serviços do ponto';
  document.querySelector('.work-items .section-heading').insertAdjacentHTML('afterend','<details class="services-filter"><summary>Filtros</summary><label class="check-label all-services"><input type="checkbox" id="allPointServices">Mostrar serviços de todos os pontos</label></details>');
  workspace.insertAdjacentHTML('afterbegin','<p id="activeServicePoint" class="active-service-point"></p><div class="movement-legend"><span class="movement-installed">+ Instalado</span><span class="movement-removed">− Desativado / retirado</span></div>');
  const summary=document.querySelector('.summary');$('tab-forms').querySelector('.page-heading').after(summary);
  summary.querySelector('h2').textContent='Totais da obra';
  summary.insertAdjacentHTML('beforebegin','<details class="card final-services"><summary>Conferir todas as mãos de obra</summary><div id="finalServices"></div></details>');
  $('tab-forms').querySelector('h1').textContent='Confira e finalize o fechamento';
  $('previewBook').textContent='Prévia do book';
  $('previewBook').className='secondary';$('previewBook').setAttribute('aria-controls','liveBookPreview');$('previewBook').setAttribute('aria-expanded','false');
  $('previewBook').onclick=()=>{const preview=$('liveBookPreview');preview.open=!preview.open;if(preview.open)preview.scrollIntoView({behavior:'smooth',block:'start'});};
  main.insertAdjacentHTML('beforeend',`<details id="liveBookPreview" class="card live-book-preview" aria-label="Pré-visualização automática do book"><summary>Prévia do book</summary><div class="section-heading"><button id="pinBookPreview" class="secondary">Fixar ao lado</button></div><p id="livePreviewStatus" role="status">Carregando prévia…</p><p class="preview-hint">O serviço entra na prévia após Adicionar ao ponto ou Aplicar alterações.</p><div class="preview-controls"><button id="previewPrevious" class="secondary" aria-label="Página anterior da prévia">←</button><label>Página<select id="previewPage"></select></label><button id="previewNext" class="secondary" aria-label="Próxima página da prévia">→</button><button id="refreshBookPreview" class="text-button">Atualizar</button></div><iframe id="liveBookFrame" title="Prévia do book durante o preenchimento" sandbox="allow-same-origin"></iframe><p id="previewError" class="notice" hidden></p></details>`);
  $('liveBookPreview').addEventListener('toggle',()=>{const open=$('liveBookPreview').open;$('previewBook').setAttribute('aria-expanded',String(open));$('previewBook').textContent=open?'Ocultar prévia':'Prévia do book';if(open){refresh();requestAnimationFrame(fitPreview);}});
  document.body.insertAdjacentHTML('beforeend','<dialog id="photoLightbox"><div class="dialog-heading"><h2>Foto de referência</h2><button id="closePhotoLightbox" class="secondary">Fechar</button></div><img id="referencePhoto" alt="Foto de referência ampliada"></dialog>');
  $('closePhotoLightbox').onclick=()=>$('photoLightbox').close();
  const enlarge=ev=>{const target=ev.target.closest('[data-photo-enlarge]');if(!target)return;if(ev.type==='keydown'&&!['Enter',' '].includes(ev.key))return;ev.preventDefault();$('referencePhoto').src=target.src;$('referencePhoto').alt=target.alt;$('photoLightbox').showModal();};
  $('pointEditor').addEventListener('click',enlarge);$('pointEditor').addEventListener('keydown',enlarge);
  $('liveBookPreview').querySelector('.section-heading').insertAdjacentHTML('beforeend','<button id="openLivePreview" class="secondary">Abrir em janela</button>');
  $('openLivePreview').onclick=()=>{popup=window.open('about:blank','engelmig-live-book','width=850,height=900,resizable=yes,scrollbars=yes');if(!popup){toast('Permita abrir a janela para acompanhar o book ao lado do cadastro.',true);return;}if(lastHTML)updatePopup();refresh();};
  $('liveBookFrame').onload=fitPreview;
  $('previewPage').onchange=()=>{page=Number($('previewPage').value);fitPreview();};
  $('previewPrevious').onclick=()=>{page=Math.max(0,page-1);fitPreview();};
  $('previewNext').onclick=()=>{page=Math.min(pages-1,page+1);fitPreview();};
  $('refreshBookPreview').onclick=()=>{revision++;refresh();};
  $('pinBookPreview').onclick=()=>{pinned=!pinned;onTab(current);};
  $('allPointServices').onchange=renderServices;
  document.addEventListener('click',ev=>{const button=ev.target.closest('[data-stage],[data-next-stage]');if(!button)return;if(button.dataset.nextStage==='work'){
   for(const id of ['workOrder','date','responsible','location'])if(!$(id).value.trim()){showTab('work');$(id).focus();$(id).reportValidity();toast('Preencha os dados da obra para continuar.',true);return;}
  }showTab(button.dataset.stage||button.dataset.destination);window.scrollTo({top:0,behavior:'smooth'});});
  window.addEventListener('resize',fitPreview);
  ready=true;onTab('work');changed();
 }
 function progress(){
  if(!ready)return;
  const b=window.Book.summary(),points=b.points;
  const flags=[['workOrder','date','responsible','location'].every(id=>$(id).value.trim()),points.length>0&&points.every(p=>p.photos.length&&S.services.some(s=>s.point_id===p.id))&&S.services.every(s=>points.some(p=>p.id===s.point_id))&&!!S.result?.ready&&(b.no_conductors||b.conductors.length>0),b.croqui_pages.length>0&&b.croqui_pages.every(p=>p.croqui&&!p.image_pending),b.forms_submitted&&!!S.lastSaved];
  for(const [i,s] of stages.entries()){const node=document.querySelector(`[data-stage="${s[0]}"]`);node.classList.toggle('complete',!!flags[i]);node.classList.toggle('current',current===s[0]);if(current===s[0])node.setAttribute('aria-current','step');else node.removeAttribute('aria-current');node.querySelector('em').textContent=flags[i]?'Preenchido':current===s[0]?'Em preenchimento':'A preencher';}
  const p=points.find(p=>p.id===window.Book.activeId());$('activeServicePoint').textContent=p?'Lançamentos do ponto '+p.number:'Cadastre um ponto para iniciar os lançamentos.';
  document.querySelector('#pointServices .workflow').hidden=!p;
  document.querySelector('#pointServices .detail-panel').hidden=!S.editor;
  for(const id of ['clearEditorChanges','removeSelectedLabor']){$(id).disabled=!(S.selected&&S.editor);$(id).title=S.editor?(id==='clearEditorChanges'?'Restaurar a composição da mão de obra aberta':'Remover somente a mão de obra aberta'):'Selecione ou edite uma mão de obra para usar esta ação';}
  if($('finalServices'))$('finalServices').innerHTML=S.services.length?S.services.map(s=>`<div class="final-service ${movementClass(s.operation)}"><strong>${esc(window.Book.serviceName(s))}</strong><span>${esc(s.operation)} · Qtd. ${esc(s.quantity)} · Ponto ${esc(points.find(p=>p.id===s.point_id)?.number||'não vinculado')}</span></div>`).join(''):'<p class="empty-table">Ainda não há serviços adicionados.</p>';
 }
 function movementClass(value){return value==='RETIRAR'||value==='desativado'?'movement-removed':value==='INSTALAR'||value==='instalado'?'movement-installed':'movement-neutral';}
 function changed(){if(!ready)return;revision++;progress();clearTimeout(timer);timer=setTimeout(refresh,1000);}
 function onTab(name){if(!ready)return;current=name;const operational=stages.some(s=>s[0]===name);$('operationStages').hidden=false;$('liveBookPreview').hidden=!operational;
  document.body.classList.toggle('preview-pinned',pinned&&operational);$('pinBookPreview').textContent=pinned?'Soltar prévia':'Fixar ao lado';progress();if(operational){clearTimeout(timer);timer=setTimeout(refresh,100);}requestAnimationFrame(fitPreview);
 }
 function fitPreview(){
  const frame=$('liveBookFrame'),doc=frame.contentDocument;if(!doc?.body||!frame.clientWidth)return;
  const articles=[...doc.querySelectorAll('.book-page')];pages=articles.length;page=Math.max(0,Math.min(page,pages-1));
  const scale=Math.min(1,(frame.clientWidth-12)/794);doc.body.style.margin='0';doc.body.style.padding='6px';
  articles.forEach((a,i)=>{a.style.display=i===page?'block':'none';a.style.margin='0 auto';a.style.zoom=String(scale);});
  for(const el of doc.querySelectorAll('.print-toolbar,.print-alert'))el.style.display='none';
  frame.style.height=(pages?1123*scale+16:160)+'px';
  $('previewPage').innerHTML=articles.map((a,i)=>`<option value="${i}" ${i===page?'selected':''}>${i+1} / ${pages} · ${esc(a.querySelector('h1')?.textContent||'Book')}</option>`).join('');
  $('previewPrevious').disabled=page<=0;$('previewNext').disabled=page>=pages-1;
 }
 async function refresh(){
  if(!ready||!S.token||(($('liveBookPreview').hidden||!$('liveBookPreview').open)&&(!popup||popup.closed)))return;
  if(running)return;running=true;const serial=revision;
  $('livePreviewStatus').textContent='Atualizando prévia…';
  try{
   const payload={...meta(true),services:S.services};
   const data=await api('/api/book-preview',payload);if(serial!==revision)return;
   if(data.html!==lastHTML){lastHTML=data.html;$('liveBookFrame').srcdoc=data.html;updatePopup();}
   $('previewError').hidden=true;$('livePreviewStatus').textContent=data.pending.length?'Prévia atualizada · '+data.pending.length+' pendência(s) para concluir.':'Prévia atualizada';
  }catch(error){if(serial!==revision)return;$('livePreviewStatus').textContent='Prévia aguardando correção';$('previewError').textContent=error.message+' A última prévia válida permanece abaixo.';$('previewError').hidden=false;}
  finally{running=false;if(serial!==revision){clearTimeout(timer);timer=setTimeout(refresh,1000);}}
 }
 function updatePopup(){
  if(!popup||popup.closed)return;
  try{const y=popup.scrollY;popup.document.open();popup.document.write(lastHTML);popup.document.close();popup.document.querySelector('#printBook')?.remove();popup.scrollTo(0,y);}catch{popup=null;}
 }
 function services(){const all=$('allPointServices')?.checked;return S.services.map((service,index)=>({service,index})).filter(({service})=>all||service.point_id===window.Book.activeId());}
 function editorShown(){if(!ready)return;$('laborFinder').open=false;}
 window.Workflow={changed,onTab,services,movementClass,editorShown,progress};
 window.addEventListener('DOMContentLoaded',install);
})();
