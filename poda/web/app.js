'use strict';
const $=id=>document.getElementById(id);
const state={os:'',date:'',qtd:'',bookType:'poda',unit:'m2',records:[],settings:{},photo:{antes:'',depois:''},activeSide:'antes',mapSelected:null,editing:-1,loading:false,materials:[],editingBookId:null,selectedMaterial:null};
let draftTimer=null,noticeTimer=null,mapReady=false,osRows=[];let osMarkers={types:[],marks:{}};let editingMarkerKey=null,materialTimer=null;
const pageTitles={book:'Novo Book fotográfico',history:'Registros de Books',os:'Ordens de Serviço',settings:'Configurações'};
function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
async function api(url,options={}){
  const response=await fetch(url,{...options,headers:{...(options.body instanceof Blob?{'Content-Type':options.body.type}:options.body?{'Content-Type':'application/json'}:{}),'X-App-Token':window.PODA_TOKEN||'',...(options.headers||{})}});
  let result;
  try{result=await response.json()}catch{throw Error('Servidor respondeu com dados inesperados.')}
  if(!response.ok)throw Error(result.error||'Falha na operação.');
  return result;
}
function toast(message,error=false){const a=$('alert');a.textContent=message;a.className='alert'+(error?' error':'');clearTimeout(noticeTimer);noticeTimer=setTimeout(()=>a.classList.add('hidden'),7500)}
function tab(id){
  document.querySelectorAll('.page').forEach(x=>x.classList.toggle('active',x.id==='page-'+id));
  document.querySelectorAll('.nav-btn').forEach(x=>x.classList.toggle('selected',x.dataset.tab===id));
  $('page-title').textContent=pageTitles[id];
  if(id==='history')loadHistory();if(id==='os')loadOS(false);if(id==='settings')showSettings();

  history.replaceState(null,'','#'+id);
}
function today(){const d=new Date();return `${String(d.getDate()).padStart(2,'0')}/${String(d.getMonth()+1).padStart(2,'0')}/${d.getFullYear()}`;}
function dateFormatting(text){let digits=String(text).replace(/\D/g,'').slice(0,8);return [digits.slice(0,2),digits.slice(2,4),digits.slice(4)].filter(Boolean).join('/');}
const serviceNames={poda:'Poda',limpeza_faixa:'Limpeza de Faixa'};
const serviceTeams={poda:'ENG PDCG02',limpeza_faixa:'ENG LFCG02'};
const unitSymbols={m2:'m²',km:'km'};
function getForm(){return {book_type:state.bookType,unit:state.bookType==='limpeza_faixa'?state.unit:'un',os:$('book-os').value.trim(),date:$('book-date').value.trim(),qtd:$('book-qtd').value,records:state.records,materials:state.materials,editing_id:state.editingBookId,pending:collectRecord(),pending_index:state.editing};}
function decimalNumber(text){
 let t=String(text||'').trim().replace(/\s/g,'');
 if(t.includes(',')&&t.includes('.'))t=t.lastIndexOf(',')>t.lastIndexOf('.')?t.replace(/\./g,'').replace(',','.'):t.replace(/,/g,'');
 else t=t.replace(',','.');
 return /^\d+(\.\d{1,4})?$/.test(t)?Number(t):NaN;
}
function measureText(v){const n=decimalNumber(v);return Number.isFinite(n)?n.toLocaleString('pt-BR',{maximumFractionDigits:4}):String(v||'')}
function updateBookTypeUI(){
 const faixa=state.bookType==='limpeza_faixa';
 $('book-type').value=state.bookType;
 $('book-os-prefix').textContent=state.bookType==='limpeza_faixa'?((state.settings&&state.settings.os_prefix_faixa)||'ENG-LFBT02.CMAD'):((state.settings&&state.settings.os_prefix)||'ENG-PDBT02.CMAD');
 $('book-unit').classList.toggle('hidden',!faixa);$('book-unit').value=state.unit;
 $('book-team').textContent=serviceTeams[state.bookType];
 $('service-header').textContent='ENGELMIG ENERGIA / '+(faixa?'LIMPEZA DE FAIXA':'PODA');
 $('book-intro').textContent=faixa?'Registre a OS, a medição em m² ou km e as fotos antes e depois de cada trecho.':'Preencha a OS, a data e inclua as evidências de cada poda.';
 $('type-hint').textContent=faixa?'Medição total em m² ou km. Equipe ENG LFCG02.':'Quantidade contabilizada por poda.';
 $('book-qtd-label').textContent=faixa?'Medição total':'Quantidade de podas';
 $('book-qtd').type=faixa?'text':'number';$('book-qtd').inputMode=faixa?'decimal':'numeric';
 $('book-qtd').placeholder=faixa?'Ex.: 1.250,5':'Auto';
 $('book-qtd-hint').textContent=faixa?'Informe o total ou preencha a medição de cada trecho.':'Quantidade total de podas.';
 $('rec-measure-wrap').classList.toggle('hidden',!faixa);
 $('rec-measure-label').textContent='Medição deste trecho ('+unitSymbols[state.unit]+')';
 $('rec-measure').placeholder=state.unit==='km'?'Ex.: 1,25':'Ex.: 250,5';
 $('add-record').textContent=(state.editing>=0?'Salvar alterações':'＋ Adicionar '+(faixa?'trecho':'poda')+' ao Book');
 $('records-heading').textContent=faixa?'Trechos deste Book':'Podas deste Book';
 $('records-caption').textContent=faixa?'Cada trecho com fotos antes/depois pode ter sua própria medição; o total será somado quando todos estiverem preenchidos.':'As podas deste Book não interferem no histórico de PDFs gerados.';
 $('page-title').textContent=faixa?'Novo Book de Limpeza de Faixa':'Novo Book fotográfico';
 updateRecords();updateDestination();
}
function changeBookType(next){
 if(next===state.bookType)return;
 if((state.records.length||$('book-os').value.trim())&&!confirm('Trocar o tipo de serviço descarta o Book em edição. Os Books já gerados permanecem no histórico. Continuar?')){
   $('book-type').value=state.bookType;return;
 }
 state.bookType=next;state.records=[];state.materials=[];state.editingBookId=null;$('book-os').value='';$('book-qtd').value='';renderMaterials();
 clearRecordFields();updateBookTypeUI();refreshEditBanner();scheduleDraft();
}
function syncFaixaTotal(){
 if(state.bookType!=='limpeza_faixa')return;
 if(state.records.length&&state.records.every(r=>String(r.measure||'').trim()&&Number.isFinite(decimalNumber(r.measure)))){
   let total=state.records.reduce((sum,r)=>sum+decimalNumber(r.measure),0);
   $('book-qtd').value=Number(total.toFixed(4)).toString().replace('.',',');
 }
}
function scheduleDraft(){clearTimeout(draftTimer);draftTimer=setTimeout(()=>api('/poda/api/draft',{method:'POST',body:JSON.stringify(getForm())}).catch(e=>console.warn('Rascunho',e)),550)}
function applyDraft(d){
  state.bookType=d.book_type==='limpeza_faixa'?'limpeza_faixa':'poda';state.unit=d.unit==='km'?'km':'m2';
  $('book-os').value=d.os||'';$('book-date').value=d.date||today();$('book-qtd').value=d.qtd||'';
  state.records=Array.isArray(d.records)?d.records:[];
  state.materials=Array.isArray(d.materials)?d.materials:[];
  state.editingBookId=d.editing_id||null;
  updateBookTypeUI();renderMaterials();refreshEditBanner();
  clearRecordFields();
  if(d.pending){
    for(const key of ['coord','td','rd','bairro','rua','measure'])$('rec-'+key).value=d.pending[key]||'';
    state.photo={antes:d.pending.antes||'',depois:d.pending.depois||''};
    state.editing=Number.isInteger(d.pending_index)&&d.pending_index>=0&&d.pending_index<state.records.length?d.pending_index:-1;
    renderPhotos();
    if(state.editing>=0)$('add-record').textContent='Salvar alterações da evidência';
  }
}
function clearRecordFields(){
  for(const field of ['coord','td','rd','bairro','rua','measure'])$('rec-'+field).value='';
  state.photo={antes:'',depois:''};state.editing=-1;renderPhotos();setActivePhoto('antes');
  updateBookTypeUI();
}
function clearBook(force=false){
  if(!force&&(state.records.length||$('book-os').value.trim())&&!confirm('Iniciar um novo Book? Os dados ainda não gerados serão descartados. Os PDFs já salvos permanecerão no histórico.'))return;
  clearTimeout(draftTimer);
  applyDraft({book_type:state.bookType,unit:state.unit,date:today(),records:[]});clearRecordFields();
  api('/poda/api/draft/clear',{method:'POST',body:'{}'}).catch(e=>toast(e.message,true));
  updateDestination();toast('Novo Book iniciado. O histórico foi preservado.');
}
function updateDestination(){
  const m=$('book-date').value.match(/^\d{2}\/([01]\d)\/(\d{4})$/);
  const names=['Janeiro','Fevereiro','Março','Abril','Maio','Junho','Julho','Agosto','Setembro','Outubro','Novembro','Dezembro'];
  $('book-dest').textContent=m&&+m[1]>=1&&+m[1]<=12?`Books / ${m[2]} / ${m[1]} - ${names[+m[1]-1]}`:'Books / Ano / Mês';
}
function setActivePhoto(side){state.activeSide=side;document.querySelectorAll('.photo-box').forEach(el=>el.classList.toggle('active',el.dataset.side===side))}
function renderPhotos(){
  for(const side of ['antes','depois']){
    const url=state.photo[side],el=$('photo-'+side),img=el.querySelector('img');
    el.classList.toggle('has-photo',!!url);img.classList.toggle('hidden',!url);
    if(url)img.src=url;else img.removeAttribute('src');
  }
}
async function upload(blob,side){
  if(!blob || !blob.type.startsWith('image/'))throw Error('Escolha uma imagem válida.');
  if(blob.size>18*1024*1024)throw Error('O limite por foto é de 18 MB.');
  const result=await api('/poda/api/upload',{method:'POST',body:blob});
  state.photo[side]=result.url;renderPhotos();scheduleDraft();
  setActivePhoto(side==='antes'?'depois':'antes');
  toast('Foto carregada.');
}
function collectRecord(){return {coord:$('rec-coord').value.trim(),td:$('rec-td').value.trim(),rd:$('rec-rd').value.trim(),bairro:$('rec-bairro').value.trim(),rua:$('rec-rua').value.trim(),measure:state.bookType==='limpeza_faixa'?$('rec-measure').value.trim():'',antes:state.photo.antes,depois:state.photo.depois}}
async function addRecord(){
  const d=collectRecord();if(!d.coord)return toast('Informe as coordenadas do serviço.',true);
  if(state.bookType==='limpeza_faixa'&&d.measure&&(!Number.isFinite(decimalNumber(d.measure))||decimalNumber(d.measure)<=0))return toast('Medição do trecho inválida. Use, por exemplo, 125,5.',true);
  if(!d.antes||!d.depois)return toast('Adicione as fotos ANTES e DEPOIS.',true);
  try{const result=await api('/poda/api/search?q='+encodeURIComponent(d.coord));if(result.type!=='coord')throw Error('Digite uma coordenada válida.')}
  catch(e){return toast(e.message,true)}
  if(state.editing>=0){state.records[state.editing]=d}
  else state.records.push(d);
  clearRecordFields();
  if(state.bookType==='poda'&&(!$('book-qtd').value||+$('book-qtd').value===state.records.length-1))$('book-qtd').value=state.records.length;
  syncFaixaTotal();updateRecords();scheduleDraft();toast((state.bookType==='limpeza_faixa'?'Trecho':'Poda')+' adicionado ao Book.');
}
function updateRecords(){
  $('records-count').textContent=state.records.length;
  const el=$('record-list'),faixa=state.bookType==='limpeza_faixa';
  if(!state.records.length){el.innerHTML='<div class="empty">Ainda não há '+(faixa?'trechos':'podas')+' neste Book.</div>';return}
  el.innerHTML=state.records.map((r,i)=>`<div class="record-row"><div class="row-number">${i+1}</div><div><b>${esc(r.td||'Sem TD')}</b><small>${esc(r.coord)}</small></div><div><b>${esc(r.rd||'Sem religador')}</b><small>${esc(r.bairro||'Bairro não informado')}</small></div><div><b>${esc(r.rua||'Rua não informada')}</b><small>${faixa&&r.measure?'Trecho: '+esc(measureText(r.measure))+' '+unitSymbols[state.unit]:'Fotos: antes / depois'}</small></div><div class="row-actions"><button class="button ghost edit-row" data-i="${i}">Editar</button><button class="button minimal delete-row" data-i="${i}">Excluir</button></div></div>`).join('');
  el.querySelectorAll('.delete-row').forEach(b=>b.onclick=()=>{
    const i=+b.dataset.i,oldCount=state.records.length;state.records.splice(i,1);
    if(!faixa&&+$('book-qtd').value===oldCount)$('book-qtd').value=state.records.length||'';
    if(faixa){if(state.records.length)syncFaixaTotal();else $('book-qtd').value=''}
    updateRecords();scheduleDraft();
  });
  el.querySelectorAll('.edit-row').forEach(b=>b.onclick=()=>{
    const r=state.records[+b.dataset.i];state.editing=+b.dataset.i;
    ['coord','td','rd','bairro','rua','measure'].forEach(k=>$('rec-'+k).value=r[k]||'');
    state.photo={antes:r.antes,depois:r.depois};renderPhotos();setActivePhoto('antes');
    $('add-record').textContent='Salvar alterações do '+(faixa?'trecho':'poda');window.scrollTo({top:240,behavior:'smooth'});
  });
}
async function generate(){
  if(!state.records.length)return toast('Adicione pelo menos uma evidência para gerar o PDF.',true);
  if(state.bookType==='limpeza_faixa'&&(!Number.isFinite(decimalNumber($('book-qtd').value))||decimalNumber($('book-qtd').value)<=0))return toast('Informe a medição total em m² ou km.',true);
  const data=getForm();let btn=$('generate-pdf');btn.disabled=true;btn.textContent='Gerando PDF...';
  try{
    clearTimeout(draftTimer);
    const endpoint=state.editingBookId?`/poda/api/books/${state.editingBookId}/edit`:'/poda/api/books/generate';
    const result=await api(endpoint,{method:'POST',body:JSON.stringify(data)});
    // O backend grava o histórico antes de apagar o rascunho.
    applyDraft({book_type:state.bookType,unit:state.unit,date:today(),records:[]});clearRecordFields();
    toast(`PDF salvo!\n${result.folder}\n${result.filename}${result.backup?'\nVersão anterior guardada: '+result.backup:''}\nO próximo Book está vazio.`);
    const win=window.open(result.pdf_url,'_blank');if(!win)console.info('PDF salvo:',result.pdf_url);
  }catch(e){toast(e.message,true);scheduleDraft()}
  finally{btn.disabled=false;refreshEditBanner()}
}
async function lookup(){
  const q=$('rec-coord').value.trim();if(!q)return toast('Digite uma coordenada.',true);
  const b=$('lookup-btn');b.disabled=true;b.textContent='Consultando...';
  try{const data=await api('/poda/api/lookup?coord='+encodeURIComponent(q));
    $('rec-coord').value=data.coord;
    for(const key of ['td','rd','bairro','rua'])if(data[key])$('rec-'+key).value=data[key];
    toast('Coordenada localizada. Confira os dados antes de adicionar.');
  }catch(e){toast(e.message,true)}finally{b.disabled=false;b.textContent='Localizar TD / Rua'}
}
async function loadHistory(){
  const q=$('history-filter').value.trim();let body=$('history-body');
  try{const result=await api('/poda/api/books?q='+encodeURIComponent(q));
    body.innerHTML=result.rows.length?result.rows.map(r=>`<tr><td><b>${r.tipo==='limpeza_faixa'?'Limpeza de Faixa':'Poda'}</b><small class="history-team">${r.tipo==='limpeza_faixa'?'ENG LFCG02':'ENG PDCG02'}</small></td><td><b>${esc(r.os)}</b></td><td>${esc(r.data)}</td><td>${r.tipo==='limpeza_faixa'?esc(Number(r.qtd).toLocaleString('pt-BR',{maximumFractionDigits:4}))+' '+(r.unidade==='km'?'km':'m²'):esc(Number(r.qtd))+' podas'}</td><td class="file-cell">${esc(r.filename)}</td><td>${esc(r.created)}</td><td><div class="actions-cell"><a href="/poda/api/books/${r.id}/pdf" target="_blank" class="button soft">Abrir PDF</a><button class="button primary edit-saved-book" data-id="${r.id}" type="button">Editar</button><button class="button ghost folder" data-id="${r.id}">Abrir pasta</button></div></td></tr>`).join(''):'<tr><td colspan="7" class="empty">Nenhum registro encontrado.</td></tr>';
    body.querySelectorAll('.edit-saved-book').forEach(b=>b.onclick=()=>editSavedBook(+b.dataset.id));
    body.querySelectorAll('.folder').forEach(b=>b.onclick=async()=>{try{const data=await api(`/poda/api/books/${b.dataset.id}/open_folder`,{method:'POST',body:'{}'});if(data.message)toast(data.message+'\n'+data.folder)}catch(e){toast(e.message,true)}});
  }catch(e){toast(e.message,true)}
}
function refreshEditBanner(){
  const editing=!!state.editingBookId;
  $('book-edit-banner').classList.toggle('hidden',!editing);
  $('generate-pdf').textContent=editing?'Salvar correções e substituir PDF':'Gerar PDF e salvar Book';
}
async function editSavedBook(id){
  if((state.records.length||state.materials.length||$('book-os').value.trim())&&!confirm('Abrir Book antigo para edição? Seu Book em andamento será substituído no formulário (não no histórico).'))return;
  try{
    const b=await api('/poda/api/books/'+id);
    if(b.payload?.legacy)throw Error('Registro importado sem fotos editáveis.');
    const d={...b.payload,book_type:b.tipo||b.payload.book_type,unit:b.unidade||b.payload.unit,
      editing_id:id,date:b.data,os:b.os,
      records:(b.payload.records||[]).map((r,i)=>({...r,antes:`/poda/api/books/${id}/photo/${i}/antes`,depois:`/poda/api/books/${id}/photo/${i}/depois`}))};
    clearTimeout(draftTimer);applyDraft(d);clearRecordFields();tab('book');scheduleDraft();
    toast('Book '+b.os+' aberto para edição. O PDF anterior será preservado em HistoricoEdicoes.');
  }catch(e){toast(e.message,true)}
}
function renderMaterials(){
  if(!$('materials-count'))return;
  $('materials-count').textContent=state.materials.length;
  const el=$('material-selected');
  if(!state.materials.length){el.innerHTML='<div class="empty">Nenhum material neste Book.</div>';return}
  el.innerHTML='<table class="material-table"><thead><tr><th>Código</th><th>Descrição</th><th>Un.</th><th>Qtd.</th><th>Ação</th></tr></thead><tbody>'+
    state.materials.map((m,i)=>`<tr><td>${esc(m.code)}</td><td>${esc(m.description)}</td><td>${esc(m.unit)}</td><td>${esc(m.qty)}</td><td><button class="button minimal remove-material" data-i="${i}">Excluir</button></td></tr>`).join('')+'</tbody></table>';
  el.querySelectorAll('.remove-material').forEach(b=>b.onclick=()=>{state.materials.splice(+b.dataset.i,1);renderMaterials();scheduleDraft()});
}
async function searchMaterials(){
  const q=$('material-search').value.trim();state.selectedMaterial=null;
  if(!q){$('material-suggestions').classList.add('hidden');return}
  try{
    const r=await api('/poda/api/materials?q='+encodeURIComponent(q));
    const el=$('material-suggestions');el.classList.remove('hidden');
    el.innerHTML=r.rows.length?r.rows.slice(0,35).map((m,i)=>`<button type="button" class="material-option" data-i="${i}"><b>${esc(m.code)}</b>${esc(m.description)} <small>${esc(m.unit||'Unidade não cadastrada')}</small></button>`).join(''):'<div class="empty">Material não encontrado.</div>';
    el.querySelectorAll('.material-option').forEach(b=>b.onclick=()=>{
      const m=r.rows[+b.dataset.i];state.selectedMaterial=m;
      $('material-search').value=m.code+' - '+m.description;
      $('material-unit').value=m.unit||'';
      el.classList.add('hidden');$('material-qty').focus();
    });
  }catch(e){toast(e.message,true)}
}
function addMaterial(){
  const m=state.selectedMaterial;if(!m)return toast('Selecione um material encontrado na pesquisa.',true);
  const qty=decimalNumber($('material-qty').value);const unit=$('material-unit').value.trim().toUpperCase();
  if(!Number.isFinite(qty)||qty<=0)return toast('Informe quantidade maior que zero.',true);
  if(!unit)return toast('Informe a unidade deste material.',true);
  state.materials.push({code:m.code,description:m.description,unit,qty:String(qty)});
  $('material-search').value='';$('material-qty').value='';$('material-unit').value='';state.selectedMaterial=null;
  $('material-suggestions').classList.add('hidden');renderMaterials();scheduleDraft();toast('Material adicionado.');
}
async function createMarker(){
  const name=$('marker-name').value.trim(),color=$('marker-color').value;
  if(!name)return toast('Informe o nome do marcador.',true);
  const key=editingMarkerKey||('m'+Date.now().toString(36));
  try{
    osMarkers=await api('/poda/api/os/marker_type',{method:'POST',body:JSON.stringify({key,label:name,color})});
    editingMarkerKey=null;$('marker-name').value='';$('marker-create').textContent='Criar marcador';
    drawMarkerLegend();renderOSRows();toast('Marcador salvo.');
  }catch(e){toast(e.message,true)}
}
async function loadMarkers(){
  osMarkers=await api('/poda/api/os/markers');drawMarkerLegend();
}
function markerStyle(key){
  const type=osMarkers.types.find(x=>x.key===key);return type?`background:${type.color}32; border:1px solid ${type.color}77`:'';
}
function drawMarkerLegend(){
  $('os-legend').innerHTML=osMarkers.types.map(t=>`<span class="os-legend-entry" style="background:${esc(t.color)}30;border:1px solid ${esc(t.color)}55"><b>${esc(t.label)}</b><button class="marker-edit" type="button" data-key="${esc(t.key)}" title="Editar">✎</button>${t.key!=='ok'?`<button class="marker-delete" type="button" data-key="${esc(t.key)}" title="Excluir">×</button>`:''}</span>`).join('');
  $('os-legend').querySelectorAll('.marker-edit').forEach(b=>b.onclick=()=>{
    const t=osMarkers.types.find(x=>x.key===b.dataset.key);editingMarkerKey=t.key;
    $('marker-name').value=t.label;$('marker-color').value=t.color;$('marker-create').textContent='Salvar marcador';
  });
  $('os-legend').querySelectorAll('.marker-delete').forEach(b=>b.onclick=async()=>{
    const key=b.dataset.key;if(!confirm('Excluir este marcador e retirar sua cor das OS?'))return;
    try{osMarkers=await api('/poda/api/os/marker_type',{method:'POST',body:JSON.stringify({action:'delete',key})});drawMarkerLegend();renderOSRows();}catch(e){toast(e.message,true)}
  });
}
function renderOSRows(){
  $('os-body').innerHTML=osRows.length?osRows.map((r,i)=>{
    const key=osMarkers.marks[r.os]||'';
    const style=markerStyle(key);
    return `<tr><td><div class="os-marker-cell"><span class="os-number" style="${style}">${esc(r.os)}</span><select class="os-status-picker" data-i="${i}" aria-label="Cor da OS ${esc(r.os)}"><option value="">Sem marcador</option>${osMarkers.types.map(t=>`<option value="${esc(t.key)}" ${t.key===key?'selected':''}>${esc(t.label)}</option>`).join('')}</select></div></td><td>${r['21307']}</td><td>${r['21308']}</td><td><b>${r.total}</b></td><td><button class="button soft select-os" data-index="${i}">Usar no Book</button></td></tr>`
  }).join(''):'<tr><td colspan="5" class="empty">Nenhuma OS com códigos 21307 e 21308.</td></tr>';
  document.querySelectorAll('.os-status-picker').forEach(e=>e.onchange=async()=>{
    const r=osRows[+e.dataset.i];try{await saveOSMark(r.os,e.value);renderOSRows()}catch(ex){toast(ex.message,true);renderOSRows()}
  });
  document.querySelectorAll('.select-os').forEach(b=>b.onclick=async()=>{
    const r=osRows[+b.dataset.index];
    if(state.editingBookId){
      if(!confirm('Você está editando um Book existente. Usar esta OS inicia um Book novo e descarta as alterações não salvas. Continuar?'))return;
      state.editingBookId=null;state.records=[];state.materials=[];renderMaterials();refreshEditBanner();
    }
    if(state.bookType==='limpeza_faixa'){
      if(state.records.length&&!confirm('As OS da planilha são de Poda. Trocar para Poda e descartar os trechos em edição?'))return;
      state.bookType='poda';state.records=[];clearRecordFields();updateBookTypeUI();
    }
    if(state.records.length&&!confirm('Substituir a OS e a quantidade atual sem excluir as podas já adicionadas?'))return;
    $('book-os').value=String(r.os).split('/')[0].trim();$('book-qtd').value=r.total;
    try{await saveOSMark(r.os,'ok')}catch(e){toast('OS selecionada, mas o marcador OK não foi salvo: '+e.message,true)}
    renderOSRows();tab('book');scheduleDraft();toast(`OS ${r.os} selecionada. Marcador: OK. Quantidade: ${r.total}.`);
  });
}
async function saveOSMark(os,key){
  const r=await api('/poda/api/os/marker',{method:'POST',body:JSON.stringify({os,key})});
  if(key)osMarkers.marks[os]=key;else delete osMarkers.marks[os];
  return r;
}
async function loadOS(force){
  $('os-state').textContent='Consultando Google Sheets...';
  try{
    const [resp]=await Promise.all([api('/poda/api/os'+(force?'?refresh=1':'')),loadMarkers()]);
    osRows=resp.rows||[];
    const stateText=resp.cached?'Dados recuperados do cache local (consulta online indisponível).':'Planilha sincronizada.';
    $('os-state').textContent=`${stateText} ${osRows.length} OS encontradas. ${resp.warning||''}`;
    renderOSRows();
  }catch(e){$('os-state').textContent=e.message;toast(e.message,true)}
}
async function showSettings(){
  try{state.settings=await api('/poda/api/settings');$('setting-dir').value=state.settings.output_dir;$('setting-prestador').value=state.settings.prestador;$('setting-prefix').value=state.settings.os_prefix;$('setting-prefix-faixa').value=state.settings.os_prefix_faixa||'';
    $('sidebar-path').textContent=state.settings.output_dir;$('book-os-prefix').textContent=state.bookType==='limpeza_faixa'?(state.settings.os_prefix_faixa||'ENG-LFBT02.CMAD'):state.settings.os_prefix;

  }catch(e){toast(e.message,true)}
}
async function saveSettings(){
  try{const result=await api('/poda/api/settings',{method:'POST',body:JSON.stringify({output_dir:$('setting-dir').value,prestador:$('setting-prestador').value,os_prefix:$('setting-prefix').value,os_prefix_faixa:$('setting-prefix-faixa').value})});
    state.settings=result;$('sidebar-path').textContent=result.output_dir;$('book-os-prefix').textContent=state.bookType==='limpeza_faixa'?(result.os_prefix_faixa||'ENG-LFBT02.CMAD'):result.os_prefix;
    toast('Configurações salvas. Novos PDFs serão enviados para a pasta configurada.');
  }catch(e){toast(e.message,true)}
}
function wire(){
  $('operation-home').onclick=async e=>{e.preventDefault();clearTimeout(draftTimer);try{await api('/poda/api/draft',{method:'POST',body:JSON.stringify(getForm())});location.href='/';}catch(error){toast(error.message,true)}};

  document.querySelectorAll('.nav-btn').forEach(b=>b.onclick=()=>tab(b.dataset.tab));
  $('book-date').addEventListener('input',e=>{e.target.value=dateFormatting(e.target.value);updateDestination();scheduleDraft()});
  ['book-os','book-qtd','rec-coord','rec-td','rec-rd','rec-bairro','rec-rua','rec-measure'].forEach(id=>$(id).addEventListener('input',scheduleDraft));
  $('book-type').onchange=e=>changeBookType(e.target.value);
  $('book-unit').onchange=e=>{
    const next=e.target.value;if(next===state.unit)return;
    if(($('book-qtd').value.trim()||state.records.some(r=>r.measure))&&!confirm('Trocar a unidade NÃO converte os valores. Limpar todas as medições e continuar?')){
      e.target.value=state.unit;return;
    }
    state.unit=next;$('book-qtd').value='';state.records.forEach(r=>r.measure='');$('rec-measure').value='';updateBookTypeUI();scheduleDraft();
  };
  $('cancel-edit').onclick=()=>clearBook(false);
  $('material-search').addEventListener('input',()=>{clearTimeout(materialTimer);materialTimer=setTimeout(searchMaterials,180)});
  $('material-add').onclick=addMaterial;
  $('marker-create').onclick=createMarker;
  $('new-book').onclick=()=>clearBook();$('add-record').onclick=addRecord;$('generate-pdf').onclick=generate;$('lookup-btn').onclick=lookup;
  for(const side of ['antes','depois']){
    const box=$('photo-'+side);box.addEventListener('click',e=>{if(!e.target.closest('button'))setActivePhoto(side)});
    box.addEventListener('dblclick',e=>{if(!e.target.closest('button')){$('photo-input').dataset.side=side;$('photo-input').click()}});
    box.addEventListener('dragenter',e=>{e.preventDefault();box.classList.add('dragover')});
    box.addEventListener('dragover',e=>{e.preventDefault()});
    box.addEventListener('dragleave',()=>box.classList.remove('dragover'));
    box.addEventListener('drop',async e=>{e.preventDefault();box.classList.remove('dragover');setActivePhoto(side);
      try{const file=[...e.dataTransfer.files].find(f=>f.type.startsWith('image/'));if(file)await upload(file,side)}catch(err){toast(err.message,true)}
    });
  }
  document.querySelectorAll('.choose-photo').forEach(b=>b.onclick=e=>{e.stopPropagation();const side=b.dataset.side;setActivePhoto(side);$('photo-input').dataset.side=side;$('photo-input').click()});
  document.querySelectorAll('.clear-photo').forEach(b=>b.onclick=e=>{e.stopPropagation();state.photo[b.dataset.side]='';renderPhotos();scheduleDraft()});
  $('photo-input').onchange=async e=>{try{if(e.target.files[0])await upload(e.target.files[0],e.target.dataset.side||state.activeSide)}catch(err){toast(err.message,true)}e.target.value=''};
  document.addEventListener('paste',async e=>{
    if(!document.getElementById('page-book').classList.contains('active'))return;
    const item=[...(e.clipboardData?.items||[])].find(v=>v.type.startsWith('image/'));
    if(!item)return;e.preventDefault();try{await upload(item.getAsFile(),state.activeSide)}catch(err){toast(err.message,true)}
  });
  $('history-refresh').onclick=loadHistory;$('history-filter').addEventListener('input',()=>{clearTimeout(draftTimer);draftTimer=setTimeout(loadHistory,300)});
  $('os-refresh').onclick=()=>loadOS(true);$('settings-save').onclick=saveSettings;
  $('modal-close').onclick=()=>$('result-modal').classList.add('hidden');
  $('result-modal').onclick=e=>{if(e.target.id==='result-modal')$('result-modal').classList.add('hidden')};
}
async function start(){
  wire();$('clock').textContent=new Date().toLocaleDateString('pt-BR',{day:'2-digit',month:'short',year:'numeric'});
  setActivePhoto('antes');
  try{
    const h=await api('/poda/api/health');window.PODA_TOKEN=h.token;$('backend-status').textContent=`online · ${h.equipment.toLocaleString('pt-BR')} equipamentos`;
    const draft=await api('/poda/api/draft');applyDraft(draft||{});await showSettings();
  }catch(e){$('backend-status').textContent='erro';toast('Servidor local: '+e.message,true)}
  const tabid=location.hash.slice(1);if(pageTitles[tabid])tab(tabid);
}
start();
