'use strict';
(() => {
 let timer,periodic,checkTimer,inFlight=null,lastSignature='',ready=false,patterns=[],notification=null,workDrafts=[];
 const payload=()=>({...meta(),services:cp(S.services),selected:S.selected,editor:S.editor?cp(S.editor):null,editing:S.editing,editor_touched:S.editorTouched});
 function status(message,error=false){const el=$('automaticStatus');if(el){el.textContent=message;el.classList.toggle('error',error);}}
 function schedule(){if(!ready)return;clearTimeout(timer);status('Salvando alterações automaticamente…');timer=setTimeout(()=>flush().catch(()=>{}),1000);}
 async function flush(force=false){
  if(!ready||!S.token)return;
  clearTimeout(timer);
  if(inFlight){await inFlight;return flush(force);}
  const data=payload(),signature=JSON.stringify(data);
  if(!force&&signature===lastSignature)return;
  inFlight=(async()=>{
   try{const saved=await api('/api/draft',{...data,record_id:crypto.randomUUID()});lastSignature=signature;
    const name=data.responsible.trim();status(`Salvo às ${new Date(saved.updated_at).toLocaleTimeString('pt-BR')} · ${name||'informe o responsável para identificar os ajustes'}`);
    if(saved.learning?.pending?.length&&$('learningPending'))$('learningPending').textContent='Rascunho salvo. Para usar no padrão: '+saved.learning.pending.join(' ');
    else if($('learningPending'))$('learningPending').textContent='';
    return saved;
   }catch(error){if(error.message.startsWith('Este rascunho foi limpo.')){ready=false;status(error.message,true);throw error;}status('Não foi possível salvar no computador. O rascunho permanece neste navegador; a gravação será tentada novamente.',true);throw error;}
   finally{inFlight=null;}
  })();return inFlight;
 }
 async function pause(){clearTimeout(timer);ready=false;if(inFlight){try{await inFlight;}catch{}}}
 function sourcePanel(){
  const list=S.patternOptions||[];
  return `<div class="learning-source"><strong>${esc(S.patternSource||'Composição em preparação')}</strong>${list.length?`<label>Configurações reconhecidas<select id="learnedChoice"><option value="">Escolha para carregar…</option>${list.map(p=>`<option value="${esc(p.id)}">${esc(p.editor.variant)} · ${p.support}/${p.uses} registros · ${fmt(p.confidence)}%</option>`).join('')}</select></label>`:''}<p id="learningPending" class="subtle"></p></div>`;
 }
 function template(){
  document.querySelector('.shell>header').insertAdjacentHTML('afterend','<div id="updateNotice" class="update-notice" role="status" hidden></div>');
  document.querySelector('.metadata').insertAdjacentHTML('afterend','<div id="automaticStatus" class="automatic-status" role="status" aria-live="polite">Salvamento automático ativo.</div>');
  const page=$('tab-profiles');
  page.querySelector('h1').textContent='Materiais aprendidos';
  page.querySelector('.page-heading p:last-child').textContent='Padrões reconhecidos nos registros de todos os responsáveis reunidos nesta instalação.';
  page.querySelector('.page-heading').insertAdjacentHTML('afterend',`<section class="card padded learning-panel"><div class="actions"><button id="refreshPatterns" class="secondary">Atualizar padrões</button><button id="exportLearning" class="secondary">Exportar registros da equipe</button><button id="importLearning" class="secondary">Reunir registros</button><button id="publishPatterns" class="primary">Baixar base para futuras versões</button><input id="learningFiles" type="file" accept=".json" multiple hidden></div><p class="muted">A sincronização busca e envia os registros da equipe pelo repositório a cada minuto. As repetições participam do padrão. A importação por arquivo continua disponível. A base para futuras versões contém composições e frequências, sem os campos de responsável, obra ou fotos.</p><p id="learningStats" class="subtle"></p><div id="learnedPatterns"></div></section>`);
  $('profileSearch').placeholder='Buscar padrão, código ou variante';
  $('allMemoryHistory').textContent='Histórico por responsável';
  page.querySelector('#profileList').insertAdjacentHTML('beforebegin','<h2 class="section-spacer">Composições das versões anteriores</h2>');
  $('historyList').insertAdjacentHTML('beforebegin','<section class="card padded section-spacer"><h2>Rascunhos automáticos por responsável</h2><p class="muted">Recupere o trabalho mesmo antes de salvar uma versão final da obra.</p><div id="workingDrafts"></div></section><h2 class="section-spacer">Versões registradas</h2>');
 }
 function renderPatterns(){
  const q=norm($('profileSearch').value),filtered=patterns.filter(p=>norm(p.editor.code+' '+p.editor.description+' '+p.editor.variant+' '+p.editor.operation).includes(q));
  $('learningStats').textContent=`${patterns.length} padrão(ões) · ${patterns.reduce((n,p)=>n+p.uses,0)} registros salvos, incluindo composições repetidas.`;
  $('learnedPatterns').innerHTML=filtered.map(p=>`<article class="pattern-card"><div class="pattern-heading"><div>${opBadge(p.editor.operation)} <strong>${esc(p.editor.code)} · ${esc(p.editor.variant)}</strong><p>${esc(p.editor.description)}</p></div><button class="secondary" data-pattern-use="${esc(p.id)}">Usar materiais</button></div><p><strong>${fmt(p.confidence)}%</strong> dos registros usam este conjunto · ${p.support} de ${p.uses} usos · ${p.different_sets} conjunto(s) encontrado(s).</p>${!p.auto_apply?'<p class="notice">Há conjuntos diferentes sem maioria. Escolha e confira os materiais desta obra.</p>':''}${p.quantity_variations>1?'<p class="subtle">As quantidades variaram. O preenchimento usa uma composição registrada desse conjunto; confira os valores para esta obra.</p>':''}<details><summary>Materiais e frequência nos registros</summary><div class="table-wrap"><table><thead><tr><th>Material</th><th>Mov.</th><th>Frequência</th><th>Quantidades por serviço observadas</th></tr></thead><tbody>${p.materials_frequency.map(m=>`<tr><td>${esc(m.code)} · ${esc(m.description)}</td><td>${esc(m.movement)}</td><td>${m.occurrences}/${p.uses} · ${fmt(m.frequency)}%</td><td>${Object.entries(m.quantities).map(([qty,count])=>`${fmt(qty)} ${esc(m.unit)} (${count})`).join(' · ')}</td></tr>`).join('')}</tbody></table></div>${p.editor.no_materials?'<p>Serviço registrado sem materiais.</p>':''}</details></article>`).join('')||'<p class="empty-table">Os padrões aparecerão conforme os responsáveis utilizarem e ajustarem as composições.</p>';
 }
 async function refresh(){await flush();patterns=await api('/api/learning/patterns');renderPatterns();}
 async function drafts(){await flush();workDrafts=await api('/api/working-drafts');$('workingDrafts').innerHTML=workDrafts.map(d=>`<div class="revision-row"><div><strong>${esc(d.work_order||'Obra não informada')}</strong><p>${esc(d.responsible||'Responsável não informado')} · ${esc(new Date(d.updated_at).toLocaleString('pt-BR'))}</p><small>${(d.services||[]).length} serviço(s) · ${(d.book?.points||[]).length} ponto(s)</small></div><button class="secondary" data-resume-draft="${esc(d.id)}">Continuar</button></div>`).join('')||'<p class="empty-table">Os trabalhos aparecem aqui automaticamente durante a edição.</p>';}
 async function resumeDraft(id){
  await window.Drawing?.flush();await flush();const d=workDrafts.find(x=>x.id===id);if(!d)return;
  S.draftId=d.draft_id;S.services=cp(d.services||[]);S.editor=d.editor?cp(d.editor):null;S.selected=d.selected;S.editing=d.editing??-1;S.editorTouched=!!d.editor_touched;S.lastSaved=null;S.patternOptions=[];S.patternSource='Rascunho automático recuperado';
  window.Book.load(d.book);for(const name of ['workOrder','date','responsible','location','notes'])$(name).value=d[name==='workOrder'?'work_order':name]||'';
  $('exports').hidden=true;renderServices();renderLabor();if(S.editor&&S.selected){prepareBaseControls();renderEditor();}else $('editor').innerHTML='<div class="empty"><h3>Rascunho recuperado</h3><p>Selecione um serviço para continuar.</p></div>';
  persist();showTab('work');await recalculate();status('Rascunho recuperado. Salvamento automático ativo.');
 }
 async function history(){
  await flush();const rows=await api('/api/learning/history');$('memoryTitle').textContent='Histórico automático por responsável';
  $('memoryContent').innerHTML='<p class="muted">Últimas 500 alterações. O histórico completo está no backup e na exportação dos registros.</p>'+rows.map(e=>`<details class="auto-history"><summary><strong>${esc(e.responsible||'Responsável não informado')}</strong> · ${esc(new Date(e.updated_at).toLocaleString('pt-BR'))} · ${esc(S.labor[e.raw.labor_id]?.code||'')} · ${esc(e.work_order||'Obra não informada')}</summary><p>${esc(e.raw.variant||'Padrão')} · ${esc(S.labor[e.raw.labor_id]?.operation||'')}</p>${e.reason?`<p class="notice">Salvo como rascunho: ${esc(e.reason)}</p>`:''}<div class="table-wrap"><table><thead><tr><th>Material</th><th>Qtd./serviço</th><th>Mov.</th></tr></thead><tbody>${(e.raw.materials||[]).map(m=>`<tr><td>${esc(S.materials[m.material_id]?.code||m.material_id)} · ${esc(S.materials[m.material_id]?.description||'')}</td><td>${esc(m.coefficient)} ${esc(m.unit)}</td><td>${esc(m.movement)}</td></tr>`).join('')}</tbody></table></div></details>`).join('');$('memoryDialog').showModal();
 }
 async function usePattern(pattern){
  const entry=crypto.randomUUID(),point_id=window.Book?.activeId()||'';
  await selectLabor(pattern.editor.labor_id,{...cp(pattern.editor),entry_id:entry,point_id,quantity:'1',reviewed:false},-1,true);
  S.patternSource=`Padrão observado em ${pattern.support} de ${pattern.uses} registros`;S.editorTouched=false;showTab('book');renderEditor();persist();
 }
 function displayNotice(data){
  const banner=$('updateNotice');
  if(!data.available){banner.hidden=true;return;}
  const key=String(data.key||data.remote_version||data.remote);
  if(sessionStorage.getItem('engelmig-update-dismissed')===key)return;
  notification=data;
  banner.innerHTML=`<div><strong>Atualização disponível${data.remote_version?' · versão '+esc(data.remote_version):''}</strong><span>${data.mode==='branch'?'Nova versão na branch '+esc(data.branch)+'.':'Nova Release publicada.'} A instalação e a reinicialização são automáticas.</span></div><button id="notificationOpen" class="primary">Ver atualização</button><button id="notificationDismiss" class="text-button" aria-label="Dispensar aviso de atualização">×</button>`;
  banner.hidden=false;
 }
 async function checkNotice(force=false){
  try{const data=await api('/api/update-notice',{force});displayNotice(data);if(force&&data.error)toast(data.error,true);return data;}catch{if(force)toast('Não foi possível verificar a atualização.',true);}
 }
 function init(data){
  patterns=data.patterns||[];ready=true;
  S.services.forEach(s=>s.entry_id=s.entry_id||crypto.randomUUID());if(S.editor)S.editor.entry_id=S.editor.entry_id||crypto.randomUUID();
  renderPatterns();schedule();
  clearInterval(periodic);periodic=setInterval(()=>flush().catch(()=>{}),30000);
  setTimeout(()=>checkNotice(),5000);clearInterval(checkTimer);checkTimer=setInterval(()=>checkNotice(),900000);
  $('allMemoryHistory').onclick=run(history);
 }
 function bind(){
  $('refreshPatterns').onclick=run(refresh);$('refreshHistory').addEventListener('click',run(drafts));$('profileSearch').addEventListener('input',renderPatterns);
  $('exportLearning').onclick=run(async()=>{await flush();location.href='/api/learning/export';});
  $('publishPatterns').onclick=run(async()=>{await flush();location.href='/api/learning/publish';});
  $('importLearning').onclick=()=>$('learningFiles').click();
  $('learningFiles').onchange=run(async ev=>{let imported=0;await flush();try{for(const file of ev.target.files){const result=await api('/api/learning/import',JSON.parse(await file.text()));imported+=result.imported_events??result.imported;}await refresh();toast(`${imported} registro(s) reunidos. Padrões atualizados.`);}finally{ev.target.value='';}});
  $('learnedPatterns').onclick=run(async ev=>{const el=ev.target.closest('[data-pattern-use]');if(el){const pattern=patterns.find(p=>p.id===el.dataset.patternUse);if(pattern)await usePattern(pattern);}});
  $('workingDrafts').onclick=run(async ev=>{const button=ev.target.closest('[data-resume-draft]');if(button)await resumeDraft(button.dataset.resumeDraft);});
  $('editor').addEventListener('change',run(async ev=>{if(ev.target.id!=='learnedChoice'||!ev.target.value)return;const p=S.patternOptions.find(x=>x.id===ev.target.value);if(!p)return;await flush();const entry_id=S.editor.entry_id,point_id=S.editor.point_id,quantity=S.editor.quantity;S.editor={...cp(p.editor),entry_id,point_id,quantity,reviewed:false};S.editorTouched=false;S.patternSource=`Padrão observado em ${p.support} de ${p.uses} registros`;prepareBaseControls();renderEditor();persist();}));
  $('updateNotice').onclick=ev=>{if(ev.target.id==='notificationDismiss'){sessionStorage.setItem('engelmig-update-dismissed',String(notification.key||notification.remote_version||notification.remote));$('updateNotice').hidden=true;}if(ev.target.id==='notificationOpen'){showTab('settings');$('applyUpdate').disabled=!notification.can_update;$('updateResult').textContent='Versão '+notification.remote_version+' disponível. Clique em Instalar atualização para baixar, atualizar e reiniciar o sistema automaticamente.';}};
  window.addEventListener('online',()=>{flush(true).catch(()=>{});checkNotice();});
  window.addEventListener('pagehide',()=>{if(!ready||!S.token)return;const body=JSON.stringify(payload());try{localStorage.setItem(localKey,JSON.stringify({...payload(),updated_at:new Date().toISOString()}));if(new Blob([body]).size<60000)fetch('/api/draft',{method:'POST',headers:{'Content-Type':'application/json','X-App-Token':S.token},body,keepalive:true}).catch(()=>{});}catch{}});
 }
 template();bind();window.Training={init,schedule,flush,pause,refreshPatterns:refresh,cancel:()=>{clearTimeout(timer);ready=false;},resume:()=>{ready=true;schedule();},sourcePanel,onTab:name=>{if(name==='profiles')run(refresh)();if(name==='history')run(drafts)();},checkNotice,clearNotice:()=>{notification=null;displayNotice({available:false});}};
})();
