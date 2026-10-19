'use strict';
// Extensão do fechamento: os materiais continuam no motor da versão 2.
(() => {
const empty=()=>({points:[],conductors:[],no_conductors:false,croqui:null,drawing:null,croqui_pages:[],forms_submitted:false,forms_note:'',point_drafts:{}});
let activeCroqui=0,croquiSwitching=false,croquiFlush=null;
let b=empty(),active='',config={},saveTimer,keepForms=false,lastGeo=null,lastBook=null,uploading=0;
const uid=()=>crypto.randomUUID().replaceAll('-','');
const point=()=>b.points.find(p=>p.id===active);
const options=(value='')=>'<option value="">Selecione o ponto</option>'+b.points.map(p=>`<option value="${esc(p.id)}" ${p.id===value?'selected':''}>Ponto ${esc(p.number)}</option>`).join('');
const touch=(preserve=false,defer=false)=>{keepForms=preserve;dirty(defer);keepForms=false;if(!defer)renderTotals();};
function currentCroqui(){return b.croqui_pages[activeCroqui];}
function pageAliases(){const page=currentCroqui();b.croqui=page?.croqui||null;b.drawing=page?.drawing||null;}
function croquiBusy(value){for(const id of ['uploadCroqui','croquiPrevious','croquiNext','croquiPage','saveCroquiPdf','removeCroqui','repairCroqui','retryCroqui'])if($(id))$(id).disabled=value;document.querySelector('.drawing-panel').inert=value;}
async function selectCroqui(index){
 if(croquiSwitching||croquiFlush||uploading||!b.croqui_pages[index]||index===activeCroqui)return;
 const owner=b;croquiSwitching=true;croquiBusy(true);
 try{await window.Drawing.flush({allowMissing:true});if(b!==owner)return;activeCroqui=index;pageAliases();renderCroqui();}finally{croquiSwitching=false;croquiBusy(false);renderCroquiNav();}
}
function renderCroquiNav(){
 const pages=b.croqui_pages;$('croquiPages').hidden=!pages.length;
 if($('repairCroqui'))$('repairCroqui').hidden=!pages.length;
 $('croquiPage').innerHTML=pages.map((page,i)=>`<option value="${i}" ${i===activeCroqui?'selected':''}>${i+1} de ${pages.length}${page.drawing?.background_source?.page?' · PDF página '+page.drawing.background_source.page:''}</option>`).join('');
 $('croquiPrevious').disabled=uploading>0||croquiSwitching||!!croquiFlush||activeCroqui===0;$('croquiNext').disabled=uploading>0||croquiSwitching||!!croquiFlush||activeCroqui>=pages.length-1;$('saveCroquiPdf').disabled=uploading>0||croquiSwitching||!!croquiFlush||!pages.length;
}
 async function flushCroquis(){
  if(croquiFlush)return croquiFlush;
  const owner=b,previous=activeCroqui;croquiBusy(true);
  croquiFlush=(async()=>{try{
   const refs=b.croqui_pages.map(p=>p.croqui?.ref).filter(Boolean);
   if(refs.length){const {missing}=await api('/api/media-check',{refs});if(b!==owner)throw Error('A obra mudou durante o salvamento do croqui.');for(const page of b.croqui_pages)if(!page.croqui?.ref||missing.includes(page.croqui.ref))page.image_pending=true;renderCroqui();}
   await window.Drawing.flush();
   for(let i=0;i<b.croqui_pages.length;i++){
    if(b!==owner)throw Error('A obra mudou durante o salvamento do croqui.');
    if(i===activeCroqui||!b.croqui_pages[i].image_pending)continue;
    activeCroqui=i;pageAliases();renderCroqui();await window.Drawing.flush();
   }
  }finally{if(b===owner&&activeCroqui!==previous){activeCroqui=previous;pageAliases();renderCroqui();}croquiFlush=null;croquiBusy(uploading>0||croquiSwitching);renderCroquiNav();}})();
  return croquiFlush;
 }
async function exportCroqui(){
 if(uploading||croquiSwitching)return;const owner=b;uploading++;croquiBusy(true);$('croquiExportStatus').textContent='Salvando a última alteração…';
 try{await flushCroquis();if(b!==owner)return;await window.CroquiExport.download(cp(b.croqui_pages),$('workOrder').value,(i,total)=>{$('croquiExportStatus').textContent=`Preparando PDF: página ${i} de ${total}…`;});$('croquiExportStatus').textContent='PDF preparado. Confira o arquivo nos downloads do navegador.';}
 finally{uploading--;croquiBusy(false);renderCroquiNav();}
}
async function importCroqui(file){
 if(Array.isArray(file)){if(file.length===1)return importCroqui(file[0]);return importCroquiImages(file);}
 if(uploading||croquiSwitching)return;const owner=b;uploading++;croquiBusy(true);
 try{
  await window.Drawing.flush({allowMissing:true});let pages;
  if(file.type==='application/pdf'||/\.pdf$/i.test(file.name)){
   let originalRef=null,metadataSize=0;
   const chosen=await window.CroquiPDF.choose(file,async item=>{
    if(b!==owner)throw Error('A obra em edição mudou. Importe o projeto novamente.');
    const ref=await api('/api/media',{name:item.name,data:item.data}),pdf={texts:item.texts,lines:item.lines};
    if(item.cleanData){const clean=await api('/api/media',{name:'Fundo PDF para edição.png',data:item.cleanData});pdf.cleanRef=clean.ref;}
    if(!originalRef)originalRef=await uploadProject(file);pdf.pdfRef=originalRef;
    const page=window.CroquiPages.page(ref,item.source,pdf);metadataSize+=new TextEncoder().encode(JSON.stringify(page)).length;if(metadataSize>20000000)throw Error('A seleção contém muitos objetos. Importe um intervalo menor de páginas.');return page;
   });
   if(!chosen)return;pages=chosen.pages;
  }else{const ref=await uploadImage(file,true);pages=[window.CroquiPages.page(ref,{kind:'image',name:file.name})];}
  if(b!==owner)return;b.croqui_pages=pages;activeCroqui=0;pageAliases();touch();renderCroqui();toast(pages.length+' página(s) importada(s). Use a navegação para editar cada página.');
 }finally{uploading--;croquiBusy(false);renderCroquiNav();}
}
async function importCroquiImages(files){
 if(uploading||croquiSwitching)return;
 if(!files.length||files.length>100)throw Error('Selecione de 1 a 100 imagens para as páginas do croqui.');
 const owner=b,pages=[];uploading++;croquiBusy(true);
 try{
  await window.Drawing.flush({allowMissing:true});
  for(const file of files){const ref=await uploadImage(file,true);if(b!==owner)throw Error('A obra mudou durante o anexo do projeto.');pages.push(window.CroquiPages.page(ref,{kind:'image',name:file.name}));}
  b.croqui_pages=pages;activeCroqui=0;pageAliases();touch();renderCroqui();toast(pages.length+' páginas de imagem adicionadas ao croqui.');
 }finally{uploading--;croquiBusy(false);renderCroquiNav();}
}
async function uploadProject(file){
 if(file.size>50*1024*1024)throw Error('Use um PDF de até 50 MB.');
 const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(Error('Não foi possível guardar o PDF original.'));reader.readAsDataURL(file);});
 return (await api('/api/project-pdf',{name:file.name,data})).ref;
}
async function repairCroqui(file){
 if(uploading||croquiSwitching||croquiFlush||!currentCroqui())return;
 if(file.size>50*1024*1024)throw Error('Use um arquivo de até 50 MB.');
 const owner=b,page=currentCroqui(),before=page.drawing;
 if(!before)throw Error('Esta página não possui um projeto editável. Use Importar imagem ou PDF.');
 const isPDF=file.type==='application/pdf'||/\.pdf$/i.test(file.name);
 if(isPDF!==(before.background_source?.kind==='pdf'))throw Error('Selecione o mesmo tipo de arquivo original desta página: '+(before.background_source?.kind==='pdf'?'PDF.':'imagem.'));
 uploading++;croquiBusy(true);$('croquiExportStatus').textContent='Recuperando a página e mantendo as edições…';
 try{
  await window.Drawing.flush({allowMissing:true});await window.Training?.flush();
  let restored;
  if(isPDF){
   if(before.pdf_source_ref){const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',await file.arrayBuffer())),x=>x.toString(16).padStart(2,'0')).join('')+'.pdf';if(hash!==before.pdf_source_ref)throw Error('Este PDF é diferente do original. Selecione o mesmo arquivo usado no projeto para manter o alinhamento das edições.');}
   const ref=await uploadProject(file),pictures=await window.PDFSource.render(ref,before.background_source,[],(before.pdf_texts||[]).length>0);
   const original=await api('/api/media',{name:file.name+' — fundo recuperado.png',data:window.CroquiQuality.pngData(pictures.original)});
   const clean=pictures.clean?await api('/api/media',{name:'Fundo de textos recuperado.png',data:window.CroquiQuality.pngData(pictures.clean)}):null;
   restored={background_ref:original.ref,pdf_text_background_ref:clean?.ref||null,pdf_source_ref:ref};
  }else{const original=await uploadImage(file,true);restored={background_ref:original.ref};}
  if(b!==owner||currentCroqui()!==page)return;
  page.drawing={...page.drawing,...restored};page.image_pending=true;pageAliases();touch();renderCroqui();await window.Drawing.flush();await window.Training?.flush();
  $('croquiExportStatus').textContent='Página recuperada. As edições foram mantidas.';toast('Arquivo original vinculado. Suas edições foram mantidas.');
 }finally{uploading--;croquiBusy(false);renderCroquiNav();}
}
function template(){
 const nav=document.querySelector('nav[aria-label="Menu principal"]');
 const work=nav.querySelector('[data-tab="work"]');
 work.insertAdjacentHTML('afterend','<button class="nav" data-tab="book"><span>02</span> Pontos e fotos</button><button class="nav" data-tab="conductors"><span>03</span> Croqui e condutores</button><button class="nav" data-tab="map"><span>04</span> Mapa QField</button><button class="nav" data-tab="forms"><span>05</span> Finalizar / Forms</button>');
 nav.insertAdjacentHTML('beforeend','<button class="nav" data-tab="settings"><span>⚙</span> Configurações</button>');
 document.querySelectorAll('[data-tab="profiles"] span,[data-tab="history"] span,[data-tab="catalog"] span').forEach(el=>el.textContent='');
 document.querySelector('main').insertAdjacentHTML('beforeend',`
 <section id="tab-book" class="tab" hidden>
  <div class="page-heading"><div><p class="eyebrow">BOOK FOTOGRÁFICO</p><h1>Pontos e fotos da obra</h1><p>Cadastre o ponto, use a foto como referência e preencha a mão de obra e os materiais ao lado.</p></div><div class="actions"><button id="previewMaterials" class="secondary">Mão de obra e materiais</button><button id="previewBook" class="primary">Visualizar book</button></div></div>
  <div class="book-workline" id="bookWorkline"></div>
  <div class="point-layout"><aside class="card points-sidebar"><div class="section-heading"><h2>Pontos</h2><button id="addPoint" class="primary">+ Ponto</button></div><div id="pointList"></div></aside><div id="pointEditor" class="card point-editor"></div><div id="pointServices"></div></div>
 </section>
 <section id="tab-conductors" class="tab" hidden>
  <div class="page-heading"><div><p class="eyebrow">COMPLEMENTOS DO BOOK</p><h1>Croqui e somagem dos condutores</h1><p>O croqui é a primeira página do book. A somagem dos condutores tem páginas próprias.</p></div></div>
  <section class="card padded attachment-zone" data-attachment-target="croqui"><div class="section-heading plain"><h2>Croqui da obra</h2><button id="uploadCroqui" class="secondary">Importar imagem ou PDF</button><input id="croquiFile" type="file" multiple accept="image/jpeg,image/png,image/webp,application/pdf,.pdf" hidden></div><p class="attachment-hint">Cole com Ctrl+V ou arraste um PDF ou imagens para esta área. Você pode escolher as páginas do PDF.</p><div id="croquiPreview"></div><div id="croquiPages" class="croqui-page-nav" hidden><button id="croquiPrevious" class="secondary">Anterior</button><label>Página do croqui<select id="croquiPage"></select></label><button id="croquiNext" class="secondary">Próxima</button><button id="saveCroquiPdf" class="primary">Salvar PDF editado</button></div><p id="croquiExportStatus" role="status" class="muted"></p><label>Observações desta página do croqui<textarea id="croquiCaption" rows="2" maxlength="2000"></textarea></label>
   <section class="drawing-panel" aria-label="Editor de textos do PDF"></section>
  </section>
  <section class="card padded section-spacer"><div class="section-heading plain"><h2>Trechos de condutores</h2></div><label class="check-label"><input id="noConductors" type="checkbox">Não houve movimentação de condutores nesta obra.</label><p class="muted">Total (m) = comprimento do trecho × número de condutores + acréscimo total em metros. Os valores ficam separados entre instalados e desativados.</p>
   <div id="conductorForm" class="conductor-form"><label>Ponto inicial<select id="cFrom"></select></label><label>Ponto final<select id="cTo"></select></label><label>Movimentação<select id="cMovement"><option value="instalado">Instalado</option><option value="desativado">Desativado</option></select></label><label>Código do material<input id="cCode" placeholder="Opcional"></label><label class="span2">Tipo / descrição<input id="cDescription" placeholder="Ex.: Cabo de alumínio protegido" maxlength="500"></label><label>Bitola<input id="cGauge" placeholder="Ex.: 50 mm²"></label><label>Comprimento do trecho (m)<input id="cLength" inputmode="decimal" placeholder="Ex.: 35,5"></label><label>Número de condutores<input id="cCount" type="number" min="1" max="100" value="1"></label><label>Acréscimo total (m)<input id="cExtra" inputmode="decimal" value="0"></label><div class="actions span2"><button id="estimateLength" class="secondary">Estimar entre coordenadas</button><button id="addConductor" class="primary">Adicionar trecho</button></div></div><div id="conductorRows"></div><div id="conductorTotals"></div><p class="muted">Esta somagem documenta os trechos. Lance os cabos também nos serviços da obra; o programa não soma novamente os trechos aos materiais para evitar duplicidade.</p>
  </section>
 </section>
 <section id="tab-map" class="tab" hidden><div class="page-heading"><div><p class="eyebrow">MESMA BASE DO BOOK PODA</p><h1>Mapa QField</h1><p>25.469 TDs e 471 religadores da base fornecida. A rede é local; o fundo de satélite depende de internet.</p></div></div>
  <div class="card padded"><div class="map-search"><input id="mapQuery" placeholder="Coordenada, TD, religador ou circuito" aria-label="Pesquisar no mapa"><button id="mapSearch" class="primary">Localizar</button><button id="mapActivePoint" class="secondary">Ponto atual</button></div><p class="muted">Ex.: -20.47, -54.62 · 20.554185°S 54.578959°W · 21K 753302 7725693 · TD-727292 · CGA51.</p><div id="mapResults"></div></div>
  <div id="mapContainer" class="card map-container"><div class="map-toolbar"><select id="mapBase" aria-label="Fundo do mapa"><option>Satélite</option><option>Mapa</option><option>Sem fundo</option></select><label class="check-label"><input id="mapTD" type="checkbox" checked>TD</label><label class="check-label"><input id="mapRD" type="checkbox" checked>Religador</label><label class="check-label"><input id="mapPost" type="checkbox">Postes</label><button id="mapFullscreen" class="secondary">Tela cheia</button><button id="mapDistance" class="secondary">Medir distância</button><button id="mapArea" class="secondary">Medir área</button><button id="mapFinish" class="secondary">Terminar medição</button><button id="mapClear" class="secondary">Limpar medição</button><button id="mapSnapshot" class="secondary">Rede para croqui</button></div><iframe id="qfieldMap" title="Mapa QField" src="/map_v11.html" loading="lazy"></iframe><div class="map-attribution"><span id="measureResult">Clique em um equipamento ou no mapa para consultar a coordenada.</span><span>Fundo: Esri · Camadas: bases QField do Book Poda</span></div></div>
 </section>
 <section id="tab-forms" class="tab" hidden><div class="page-heading"><div><p class="eyebrow">ETAPA FINAL</p><h1>Conferência e Forms</h1><p>Gere o book, preencha o formulário e registre a conclusão.</p></div></div><div class="card padded"><div id="bookChecklist"></div><div class="actions"><button id="formsPreview" class="primary">Salvar e visualizar book</button><button id="copyForms" class="secondary">Copiar resumo da obra</button><a id="openForms" class="secondary link-button" target="_blank" rel="noopener noreferrer">Abrir link do formulário</a></div><p id="formsLinkHint" class="notice"></p><label class="check-label"><input id="formsSubmitted" type="checkbox">Já preenchi e enviei o formulário externo desta obra.</label><label>Protocolo / observação do envio<input id="formsNote" maxlength="1000" placeholder="Opcional"></label><button id="saveForms" class="primary section-spacer">Salvar conclusão</button><p class="muted">A marcação registra sua confirmação. O programa não envia respostas nem consulta o comprovante do Microsoft Forms.</p><textarea id="formsCopyFallback" rows="10" readonly hidden aria-label="Resumo para copiar"></textarea></div></section>
 <section id="tab-settings" class="tab" hidden><div class="page-heading"><div><p class="eyebrow">PREFERÊNCIAS</p><h1>Configurações</h1><p>Formulário, consulta da rede e atualização do programa.</p></div></div><div class="card padded"><div class="settings-grid"><label class="span2">Link do Forms ou mensagem com o formulário<input id="settingForms" type="url"></label><label>Raio da busca de TD e religador (metros)<input id="settingRadius" type="number" min="50" max="20000"></label><label>Fundo inicial do mapa<select id="settingBase"><option>Satélite</option><option>Mapa</option><option>Sem fundo</option></select></label><label class="span2">Repositório GitHub<input id="settingRepo" type="url"></label><label>Branch do programa<input id="settingBranch" value="main"></label><label>Branch dos registros<input id="settingSyncBranch" value="registros-materiais"></label><label class="check-label span2"><input id="settingSyncEnabled" type="checkbox" checked>Sincronizar automaticamente os registros da equipe pelo repositório</label></div><button id="saveSettings" class="primary">Salvar configurações</button></div><div class="card padded section-spacer"><h2>Atualização pelo GitHub</h2><p>O programa consulta a última Release. Sem Release, consulta a última tag de versão; sem tags, consulta a branch do programa.</p><p class="muted">Após o download, um BAT independente fecha o servidor, substitui os arquivos do programa preservando dados/, e inicia novamente. Para disponibilizar uma atualização, alinhe a versão em app.py e version.json, envie os arquivos e publique a tag correspondente (ou uma Release). O repositório precisa estar público para consulta sem autenticação.</p><div class="actions"><button id="checkUpdate" class="secondary">Verificar atualização</button><button id="applyUpdate" class="primary" disabled>Instalar atualização</button></div><pre id="updateResult" class="update-result"></pre></div></section>`);
 $('exports').insertAdjacentHTML('beforeend','<button id="exportBook" class="secondary">Book fotográfico / PDF</button><button id="exportMaterials" class="secondary">Mão de obra e materiais / PDF</button>');
 document.querySelector('#tab-help .help').insertAdjacentHTML('afterbegin','<h2>Como usar o book</h2><ol><li>Preencha número da obra, data, responsável e local na etapa 1.</li><li>Na etapa 2, adicione os pontos e fotos. Preencha a mão de obra e os materiais ao lado da foto. Verde indica instalado; laranja indica desativado. Adicione o serviço ao ponto para incluí-lo no book. Composições abertas são preservadas ao trocar de ponto.</li><li>Adicione o croqui e os trechos de condutores. Se não houve cabos, marque a opção correspondente.</li><li>Visualize o book com o croqui na primeira página e as mãos de obra instaladas/desativadas. Use Mão de obra e materiais para o documento separado com os totais ou a opção CSV para Excel.</li><li>No croqui, importe uma página, todas ou um intervalo do PDF. Alterne as páginas pelo seletor. Role a roda para ampliar e segure o botão do meio para arrastar a visualização. Use a barra lateral para inserir símbolos e linhas, renomear e ajustar a escala. Clique nas letras para editar e arraste a alça acima do texto para mover. Textos, símbolos e linhas são selecionados juntos. Use os cantos da seleção para redimensionar e ↻ para girar. Esc ou clique vazio desmarca. Criar / editar simbologia abre os modelos pessoais, salvos automaticamente. Pesquisar no PDF localiza informações na página atual ou nas páginas importadas. Salvar PDF editado baixa o croqui separado. As alterações são salvas automaticamente. Limpar alterações do PDF restaura a página importada; Desfazer recupera a edição. PDFs escaneados não possuem texto selecionável; não há OCR nesta versão.</li><li>Na etapa Finalizar / Forms, abra o link, preencha o formulário e registre sua confirmação.</li></ol><p>A consulta por coordenada apresenta equipamentos próximos. Proximidade não determina a ligação elétrica ou o religador responsável: confira a rede antes de usar a referência.</p><p>Limpar rascunho atual apaga apenas o fechamento em edição, inclusive a cópia automática. As versões registradas no histórico, outros rascunhos e os padrões de materiais são mantidos. O backup completo inclui fotos, croqui, rascunho, configurações e registros. Preserve a pasta dados ao atualizar.</p>');
}
function init(settings){config=settings;loadSettings();renderPoints();renderConductors();renderCroqui();renderTotals();setupDrawing();}
function load(data){window.Drawing?.resetSearch?.();b={...empty(),...(data?cp(data):{})};b.point_drafts=b.point_drafts||{};b.points=b.points||[];b.conductors=b.conductors||[];b.croqui_pages=window.CroquiPages.fromBook(data||{});activeCroqui=0;pageAliases();active=b.points[0]?.id||'';lastBook=data?cp(data):null;editingConductor=-1;if($('pointList')){$('addConductor').textContent='Adicionar trecho';renderPoints();renderConductors();renderCroqui();renderTotals();}}
function autosave(){if(window.Training)return window.Training.schedule();clearTimeout(saveTimer);saveTimer=setTimeout(async()=>{if(!S.token)return;try{await api('/api/draft',{...meta(),services:S.services,selected:S.selected,editor:S.editor,editing:S.editing});}catch(e){toast('Não foi possível gravar o rascunho no computador: '+e.message,true);}},900);}
function invalidateForms(){if(!keepForms)b.forms_submitted=false;lastBook=null;if($('formsSubmitted'))$('formsSubmitted').checked=b.forms_submitted;}
function onTab(name){if(name==='book'){activateEditorPoint();renderPoints();renderServices();renderTotals();}if(name==='conductors'){renderConductors();renderCroqui();run(async()=>{await checkBook();renderConductors();})();}if(name==='forms'){renderTotals();run(checkBook)();}if(name==='map')setTimeout(syncMap,150);}
function pointFields(p,reference=false){return (reference?[['TD','td',100],['Religador','rd',100],['Circuito','circuit',100]]:[['Número do ponto','number',60],['Coordenada','coordinate',200]]).map(([label,key,max])=>`<label class="${key==='coordinate'?'coordinate-field':''}">${label}<input data-pfield="${key}" value="${esc(p[key])}" maxlength="${max}" ${key==='coordinate'?'placeholder="21K 753302 7725693 ou latitude, longitude"':''}></label>`).join('');}
function renderPointList(){
 $('pointList').innerHTML=b.points.map((p,i)=>`<button class="point-item ${p.id===active?'selected':''}" data-point="${esc(p.id)}"><strong>Ponto ${esc(p.number||i+1)}</strong><small>${p.photos.length} foto(s) · ${S.services.filter(s=>s.point_id===p.id).length} serviço(s)${b.point_drafts?.[p.id]?' · composição em rascunho':''}</small></button>`).join('')||'<p class="empty-table">Adicione o primeiro ponto.</p>';
}
function renderPoints(){
 renderPointList();const p=point();
 if(!p){$('pointEditor').innerHTML='<div class="empty"><h3>Cadastre o primeiro ponto</h3><p>Clique em + Ponto. Adicione a foto e preencha os serviços ao lado.</p></div>';window.Workflow?.progress();return;}
 $('pointEditor').innerHTML=`<div class="section-heading plain"><h2>Ponto ${esc(p.number)}</h2><div class="actions"><button id="pointUp" class="secondary" title="Mover ponto para cima">↑</button><button id="pointDown" class="secondary" title="Mover ponto para baixo">↓</button><button id="removePoint" class="text-button">Excluir</button></div></div><div class="point-fields">${pointFields(p)}</div><div class="actions"><button id="lookupPoint" class="secondary">Localizar pela coordenada</button></div><div id="pointGeoResult"></div><details class="source-detail"><summary>Referências da rede e dados do equipamento</summary><div class="point-fields">${pointFields(p,true)}${[['Patrimônio','patrimony'],['Série','serial'],['Tensão','voltage'],['Potência','power'],['Impedância','impedance'],['Fabricante','manufacturer'],['Data de fabricação','manufactured']].map(([label,key])=>`<label>${label}<input data-pfield="${key}" value="${esc(p[key]||'')}" maxlength="100"></label>`).join('')}</div><p class="subtle">TD, religador e circuito ficam no cadastro e não são impressos no book. Confira as referências encontradas por proximidade.</p></details><div class="photo-reference attachment-zone" data-attachment-target="photos"><div class="section-heading plain"><h2>Foto de referência</h2><button id="uploadPhotos" class="primary">+ Fotos</button><input id="photosFile" type="file" accept="image/jpeg,image/png,image/webp" multiple hidden></div><p class="photo-enlarge-hint">Cole imagens com Ctrl+V ou arraste arquivos para esta área. Clique na foto para ampliar.</p><div id="photoStatus" class="muted"></div><div class="photo-cards">${p.photos.map((ph,i)=>`<div class="photo-card"><img src="/media/${esc(ph.ref)}" data-photo-enlarge="${i}" tabindex="0" role="button" aria-label="Ampliar foto ${i+1} do ponto ${esc(p.number)}" alt="Foto ${i+1} do ponto ${esc(p.number)}"><div class="photo-card-fields"><select data-photo="${i}" data-photo-field="stage" aria-label="Etapa da foto">${['Antes','Depois','Detalhe'].map(v=>`<option ${v===ph.stage?'selected':''}>${v}</option>`).join('')}</select><input data-photo="${i}" data-photo-field="caption" value="${esc(ph.caption)}" maxlength="500" placeholder="Legenda da foto"><div class="actions"><button class="text-button" data-photo-up="${i}" aria-label="Mover foto ${i+1} para cima">↑</button><button class="text-button" data-photo-down="${i}" aria-label="Mover foto ${i+1} para baixo">↓</button><button class="text-button" data-photo-remove="${i}">Remover foto</button></div></div></div>`).join('')||'<p class="empty-table">Adicione as fotos deste ponto para usar como referência.</p>'}</div></div><div class="point-texts"><label class="movement-installed">Observações de instalação<textarea data-pfield="installed" rows="2" maxlength="3000">${esc(p.installed)}</textarea></label><label class="movement-removed">Observações de desativação<textarea data-pfield="removed" rows="2" maxlength="3000">${esc(p.removed)}</textarea></label></div><label>Observações do ponto<textarea data-pfield="notes" rows="2" maxlength="6000">${esc(p.notes)}</textarea></label>`;
 window.Workflow?.progress();
}
let switchingPoint=false;
async function selectPoint(id){
 if(switchingPoint||id===active||!b.points.some(p=>p.id===id))return;
 switchingPoint=true;
 try{
  await window.Training?.flush();
  if(S.editor&&S.selected){const owner=S.editor.point_id||active;b.point_drafts[owner]={editor:cp(S.editor),selected:S.selected,editing:S.editing,editor_touched:S.editorTouched,patternOptions:cp(S.patternOptions||[]),patternSource:S.patternSource||''};}
  active=id;const saved=b.point_drafts[id];delete b.point_drafts[id];
  S.editor=saved?.editor||null;S.selected=saved?.selected||null;S.editorTouched=!!saved?.editor_touched;S.editing=saved?.editing>=0?S.services.findIndex(s=>s.entry_id&&s.entry_id===saved.editor.entry_id):-1;
  S.groups=[];S.patternOptions=saved?.patternOptions||[];S.patternSource=saved?.patternSource||'';
  if(S.editor){prepareBaseControls();renderEditor();}else{$('editorMode').textContent='';$('editor').innerHTML='<div class="empty"><h3>Adicione os serviços deste ponto</h3><p>Abra Buscar e adicionar mão de obra e confira os materiais usando a foto.</p></div>';}
  if($('laborFinder'))$('laborFinder').open=!S.editor;
  renderPoints();renderLabor();renderServices();persist();if(S.selected)await loadSuggestions(S.selected);
 }finally{switchingPoint=false;}
}
function activateEditorPoint(){if(S.editor?.point_id&&b.points.some(p=>p.id===S.editor.point_id)){active=S.editor.point_id;delete b.point_drafts[active];renderPoints();renderServices();}}
function bookServiceName(s){const base=S.bases.find(b=>b.id===s.base_id);return base?.kind==='structure'?'Estrutura '+base.params.structure+' · poste '+base.params.pole+(s.context?' · '+s.context:''):s.description||S.labor[s.labor_id]?.description||'';}
function renderPointMaterials(){window.Workflow?.progress();}
async function addPoint(){await window.Training?.flush();let number=1;while(b.points.some(p=>p.number===String(number)))number++;const p={id:'p_'+uid(),number:String(number),coordinate:'',td:'',rd:'',circuit:'',network_source:'informado',installed:'',removed:'',notes:'',photos:[]};b.points.push(p);await selectPoint(p.id);touch();renderPoints();renderServices();}
async function uploadImage(file,project=false){
 if(!file.type.startsWith('image/'))throw Error('Escolha uma imagem JPG, PNG ou WebP.');
 const bitmap=await createImageBitmap(file).catch(()=>{throw Error('Não foi possível abrir a imagem. Converta para JPG ou PNG.');});
 let canvas;
 try{
  const ratio=Math.min(1,1800/Math.max(bitmap.width,bitmap.height)),size=project?window.CroquiQuality.sourceSize(bitmap.width,bitmap.height):{width:Math.max(1,Math.round(bitmap.width*ratio)),height:Math.max(1,Math.round(bitmap.height*ratio))};
  const c=canvas=document.createElement('canvas');c.width=size.width;c.height=size.height;const ctx=c.getContext('2d');ctx.imageSmoothingQuality='high';ctx.fillStyle='#fff';ctx.fillRect(0,0,c.width,c.height);ctx.drawImage(bitmap,0,0,c.width,c.height);
  return await api('/api/media',{name:file.name,data:project?window.CroquiQuality.pngData(c):c.toDataURL('image/jpeg',.88)});
 }finally{bitmap.close();if(canvas)canvas.width=canvas.height=1;}
}
async function uploadPhotos(files,pointId=active){const owner=b,p=b.points.find(p=>p.id===pointId);if(!p)throw Error('Selecione um ponto antes de anexar as fotos.');if(p.photos.length+files.length>30)throw Error('Limite de 30 fotos por ponto.');uploading++;try{for(let i=0;i<files.length;i++){if($('photoStatus'))$('photoStatus').textContent=`Salvando foto ${i+1} de ${files.length}…`;const ref=await uploadImage(files[i]);if(b!==owner||!b.points.includes(p))throw Error('A obra ou o ponto mudou durante o anexo das fotos.');p.photos.push({...ref,caption:'',stage:'Detalhe'});touch();}renderPoints();toast('Fotos guardadas no computador.');}finally{uploading--;if($('photoStatus'))$('photoStatus').textContent='';}}
function renderCroqui(reload=true){const c=b.croqui;$('croquiPreview').innerHTML=c?`<p class="muted">Selecione textos, símbolos e linhas na página abaixo. A edição é salva automaticamente.</p><button id="removeCroqui" class="text-button">Remover esta página</button>`:'<p class="empty-table">Importe um PDF ou uma imagem do croqui. As camadas do mapa também podem ser usadas.</p>';$('croquiCaption').value=c?.caption||'';renderCroquiNav();if(reload)window.Drawing?.load(b.drawing,c?.ref,currentCroqui()?.image_pending===true);}
function renderConductors(){const from=$('cFrom').value,to=$('cTo').value;$('cFrom').innerHTML=options(from);$('cTo').innerHTML=options(to);$('noConductors').checked=b.no_conductors;$('conductorForm').hidden=b.no_conductors;const names=Object.fromEntries(b.points.map(p=>[p.id,p.number]));
 $('conductorRows').innerHTML=b.conductors.length?'<div class="table-wrap"><table><thead><tr><th>Trecho</th><th>Condutor</th><th>Mov.</th><th>Comprimento</th><th>Nº</th><th>Acréscimo</th><th>Total m</th><th></th></tr></thead><tbody>'+b.conductors.map((c,i)=>`<tr><td>${esc(names[c.from_point])} → ${esc(names[c.to_point])}</td><td>${esc(c.code)} ${esc(c.description)}<small>${esc(c.gauge)}</small></td><td>${esc(c.movement)}</td><td>${fmt(c.length)}</td><td>${c.count}</td><td>${fmt(c.extra)}</td><td>${fmt(c.total??0)}</td><td><button class="text-button" data-edit-conductor="${i}">Editar</button><button class="text-button" data-remove-conductor="${i}">Remover</button></td></tr>`).join('')+'</tbody></table></div>':'<p class="empty-table">Nenhum trecho lançado.</p>';
 $('conductorTotals').innerHTML=(lastBook?.conductor_totals||[]).map(c=>`<p><strong>${esc(c.movement)} · ${esc(c.code)} ${esc(c.description)} ${esc(c.gauge)}: ${fmt(c.total)} m</strong></p>`).join('');
}
let editingConductor=-1;
async function addConductor(){const row={id:editingConductor>=0?b.conductors[editingConductor].id:'c_'+uid(),from_point:$('cFrom').value,to_point:$('cTo').value,movement:$('cMovement').value,code:$('cCode').value.trim(),description:$('cDescription').value.trim(),gauge:$('cGauge').value.trim(),length:$('cLength').value,count:$('cCount').value,extra:$('cExtra').value||'0'};
 const trial=cp(b);trial.no_conductors=false;if(editingConductor>=0)trial.conductors[editingConductor]=row;else trial.conductors.push(row);
 const checked=await api('/api/book-check',{book:trial,services:S.services});b.conductors=checked.conductors;b.no_conductors=false;editingConductor=-1;$('addConductor').textContent='Adicionar trecho';touch();lastBook=checked;renderConductors();toast('Trecho incluído na somagem.');}
function editConductor(i){editingConductor=i;const c=b.conductors[i];for(const [field,id] of [['from_point','cFrom'],['to_point','cTo'],['movement','cMovement'],['code','cCode'],['description','cDescription'],['gauge','cGauge'],['length','cLength'],['count','cCount'],['extra','cExtra']])$(id).value=c[field];$('addConductor').textContent='Salvar alterações do trecho';$('conductorForm').scrollIntoView({behavior:'smooth'});}
async function estimate(){const a=b.points.find(p=>p.id===$('cFrom').value),z=b.points.find(p=>p.id===$('cTo').value);if(!a?.coordinate||!z?.coordinate)throw Error('Informe coordenadas dos dois pontos.');const [pa,pz]=await Promise.all([api('/api/geo?q='+encodeURIComponent(a.coordinate)),api('/api/geo?q='+encodeURIComponent(z.coordinate))]);if(pa.type!=='coord'||pz.type!=='coord')throw Error('Coordenadas inválidas.');const rad=Math.PI/180,h=Math.sin((pz.lat-pa.lat)*rad/2)**2+Math.cos(pa.lat*rad)*Math.cos(pz.lat*rad)*Math.sin((pz.lon-pa.lon)*rad/2)**2;$('cLength').value=(12742000*Math.asin(Math.sqrt(h))).toFixed(2);toast('Distância geográfica estimada. Confira o comprimento real do cabo, incluindo flechas e descidas.');}
async function checkBook(){if(!S.catalog)return;try{const checked=await api('/api/book-check',{book:window.Book.value(),services:S.services});lastBook=checked;renderTotals();return checked;}catch(e){$('bookChecklist').innerHTML='<div class="notice">'+esc(e.message)+'</div>';throw e;}}
function renderTotals(){if(!$('bookChecklist'))return;const photos=b.points.reduce((n,p)=>n+p.photos.length,0);$('bookWorkline').textContent=`Obra ${$('workOrder').value||'não informada'} · ${b.points.length} pontos · ${photos} fotos`;
 const pending=lastBook?.pending||[];const items=[['Pontos com fotos',b.points.length>0&&b.points.every(p=>p.photos.length)],['Serviços vinculados aos pontos',S.services.length>0&&S.services.every(s=>b.points.some(p=>p.id===s.point_id))],['Composições conferidas',!!S.result?.ready],['Croqui',!!b.croqui],['Somagem dos condutores',b.conductors.length>0||b.no_conductors],['Formulário externo enviado',b.forms_submitted]];
 $('bookChecklist').innerHTML='<div class="book-checks">'+items.map(([label,ok])=>`<div><span class="pill ${ok?'good':'warn'}">${ok?'OK':'Pendente'}</span> ${label}</div>`).join('')+'</div>'+(pending.length?'<p class="notice">'+pending.map(esc).join('<br>')+'</p>':'');
 $('formsSubmitted').checked=b.forms_submitted;$('formsNote').value=b.forms_note;$('openForms').href=config.forms_url||'#';$('openForms').hidden=!config.forms_url;
 $('formsLinkHint').textContent=config.forms_url?.includes('teams.microsoft.com')?'O link configurado abre a mensagem do Teams. Abra o Forms contido nela. Você pode cadastrar o link direto em Configurações.':config.forms_url?'O Forms será aberto no navegador e poderá pedir seu login da empresa. Use o resumo para auxiliar o preenchimento.':'Cadastre o link do formulário em Configurações.';renderPointMaterials();
}
async function previewReport(route='/book'){if(uploading)throw Error('Aguarde o término do envio das imagens.');const popup=window.open('about:blank','_blank');try{const job=await saveJob('rascunho');if(!job){popup?.close();return;}const url=route+'?id='+encodeURIComponent(job.id);if(popup)popup.location.href=url;else toast('Book salvo. Use o botão Book fotográfico / PDF no fechamento.');}catch(e){popup?.close();throw e;}}
async function preview(){return previewReport('/book');}
function afterSave(job){if(job.book){lastBook=job.book;if(job.workflow==='aguardando_forms'){$('saveStatus').textContent='Book salvo. Formulário externo pendente.';showTab('forms');}renderTotals();}}
async function copySummary(){const job=await saveJob('rascunho');if(!job)return;const data=await api('/api/summary?id='+encodeURIComponent(job.id));try{await navigator.clipboard.writeText(data.text);toast('Resumo copiado.');}catch{$('formsCopyFallback').hidden=false;$('formsCopyFallback').value=data.text;$('formsCopyFallback').select();toast('Selecione e copie o resumo abaixo.');}}
function loadSettings(){for(const [id,key] of [['settingForms','forms_url'],['settingRadius','radius_m'],['settingBase','map_base'],['settingRepo','repository'],['settingBranch','branch'],['settingSyncBranch','sync_branch']])$(id).value=config[key]??'';$('settingSyncEnabled').checked=config.sync_enabled!==false;$('mapBase').value=config.map_base||'Satélite';renderTotals();}
function settingsPayload(){return {forms_url:$('settingForms').value,radius_m:$('settingRadius').value,map_base:$('settingBase').value,repository:$('settingRepo').value,branch:$('settingBranch').value,sync_branch:$('settingSyncBranch').value,sync_enabled:$('settingSyncEnabled').checked};}
let repositoryCheck=0;
async function testRepository(){
 const ticket=++repositoryCheck;$('repositoryCheckResult').textContent='Verificando acesso de leitura ao repositório…';$('testRepository').disabled=true;
 try{const result=await api('/api/repository-check',settingsPayload());if(ticket!==repositoryCheck)return;$('repositoryCheckResult').textContent=result.message+(result.found?' O envio dos registros usa a conta configurada no Git deste computador.':'');$('repositoryCheckResult').classList.toggle('error',result.found===false);}
 catch(error){if(ticket===repositoryCheck)$('repositoryCheckResult').textContent=error.message;}
 finally{if(ticket===repositoryCheck)$('testRepository').disabled=false;}
}
async function saveSettings(){config=await api('/api/settings',settingsPayload());loadSettings();syncMap();window.RecordSyncUI?.refresh();window.Training?.clearNotice?.();$('applyUpdate').disabled=true;$('updateResult').textContent='Endereço salvo. Use Verificar atualização para consultar esta configuração.';toast('Configurações salvas.');testRepository();}
const mapWindow=()=>$('qfieldMap').contentWindow;
function syncMap(){const w=mapWindow();if(!w?.setLayerVisibility)return;w.setBaseMap($('mapBase').value);w.setLayerVisibility($('mapTD').checked,$('mapRD').checked,$('mapPost').checked);const ps=b.points.filter(p=>Number.isFinite(p.lat)&&Number.isFinite(p.lon));w.setEvidenceData(ps.map(p=>({id:p.id,title:'Ponto '+p.number,lat:p.lat,lon:p.lon,complete:!!p.photos.length})));w.requestViewport();}
function geoDisplay(data,target='mapResults'){
 lastGeo=data;const el=$(target);let html='';
 if(data.type==='coord'){mapWindow()?.showSearchMarker?.(data.lat,data.lon,17);const refs=[...(data.nearest?.td||[]).slice(0,1),...(data.nearest?.rd||[]).slice(0,1)];html=`<p><strong>${esc(data.utm||data.lat.toFixed(8)+", "+data.lon.toFixed(8))}</strong></p><p class="muted">Raio: ${fmt(data.radius_m||config.radius_m)} m. Equipamentos próximos são referências para conferência da ligação elétrica.</p>`+refs.map(r=>`<p>${esc(r.kind)} <strong>${esc(r.code)}</strong> · ${fmt(r.distance_m)} m · Circuito ${esc(r.circuit||'não informado')}</p>`).join('');if(!refs.length)html+='<p class="notice">Nenhum TD ou religador no raio configurado.</p>';html+='<button class="secondary" data-use-geo="coord">Aplicar coordenada e referências ao ponto atual</button>';}
 else html='<div class="geo-results">'+data.results.map((r,i)=>`<div><strong>${esc(r.code)}</strong> · ${esc(r.circuit)} <small>${esc(r.utm||r.lat.toFixed(6)+", "+r.lon.toFixed(6))}</small><button class="secondary" data-map-result="${i}">Ver no mapa</button><button class="secondary" data-use-geo="${i}">Usar no ponto</button></div>`).join('')+'</div>';
 el.innerHTML=html;
}
async function lookupPoint(){const p=point();if(!p?.coordinate)throw Error('Informe a coordenada do ponto.');const data=await api('/api/geo?q='+encodeURIComponent(p.coordinate));if(data.type!=='coord')throw Error('Informe uma coordenada válida no campo do ponto.');p.lat=data.lat;p.lon=data.lon;p.coordinate=data.utm||p.coordinate;const field=document.querySelector('[data-pfield="coordinate"]');if(field)field.value=p.coordinate;touch();geoDisplay(data,'pointGeoResult');}
async function mapSearch(){geoDisplay(await api('/api/geo?q='+encodeURIComponent($('mapQuery').value)));}
async function useGeo(index){let p=point();if(!p){await addPoint();p=point();}const d=index==='coord'?lastGeo:lastGeo.results[Number(index)];p.lat=d.lat;p.lon=d.lon;p.coordinate=d.utm||d.lat.toFixed(8)+', '+d.lon.toFixed(8);if(index==='coord'){p.td=d.nearest.td[0]?.code||'';p.rd=d.nearest.rd[0]?.code||'';p.circuit=d.nearest.td[0]?.circuit||d.nearest.rd[0]?.circuit||'';p.network_source='proximidade';}else{p[d.kind==='TD'?'td':'rd']=d.code;p.circuit=d.circuit;p.network_source='informado';}touch();renderPoints();syncMap();toast('Referência aplicada ao ponto '+p.number+'.');}
function setupDrawing(){window.Drawing.init({
 getPages:()=>b.croqui_pages,getPageId:()=>currentCroqui()?.id,
 onBackgroundStatus:state=>{if(!$('croquiRecovery'))return;$('croquiRecovery').hidden=!state.error;$('croquiRecoveryMessage').textContent=state.error?state.error+' Use Vincular arquivo original para recuperar esta página mantendo as edições.':'';},
 onRecover:async(original,clean)=>{
  const saved=await api('/api/media',{name:'Fundo do croqui recuperado.png',data:window.CroquiQuality.pngData(original)});
  const text=clean?await api('/api/media',{name:'Fundo de textos recuperado.png',data:window.CroquiQuality.pngData(clean)}):null;
  return {original:saved.ref,clean:text?.ref||null};
 },
 onSearchPage:async id=>{const index=b.croqui_pages.findIndex(p=>p.id===id);if(index>=0)await selectCroqui(index);},
 onChange:doc=>{let page=currentCroqui();if(!page){page={id:window.CroquiPages.id(),croqui:null,drawing:null};b.croqui_pages.push(page);activeCroqui=b.croqui_pages.length-1;}page.drawing=doc;page.image_pending=true;pageAliases();touch(false,true);},
 onUnchanged:snapshot=>{const page=currentCroqui();if(page?.drawing===snapshot&&page.image_pending){delete page.image_pending;touch();renderCroqui(false);}},
 onImage:async(data,signature,snapshot)=>{
  const owner=b,page=currentCroqui();if(!page||(snapshot&&page.drawing!==snapshot))return;
  const ref=await api('/api/media',{name:'Croqui editável.png',data});
  if(b!==owner||(snapshot?page.drawing!==snapshot:JSON.stringify(page.drawing)!==signature))return;
  page.croqui={...ref,caption:page.croqui?.caption||''};delete page.image_pending;pageAliases();touch();renderCroqui(false);
 }
 });window.Drawing.load(b.drawing,b.croqui?.ref,currentCroqui()?.image_pending===true);
}
function bind(){
 $('addPoint').onclick=run(addPoint);$('pointList').onclick=run(async ev=>{const el=ev.target.closest('[data-point]');if(el)await selectPoint(el.dataset.point);});
 $('pointEditor').addEventListener('input',ev=>{const t=ev.target,p=point();if(!p)return;if(t.dataset.pfield){p[t.dataset.pfield]=t.value;if(t.dataset.pfield==='number')renderPointList();if(t.dataset.pfield==='coordinate'){p.lat=p.lon=null;}if(['td','rd','circuit'].includes(t.dataset.pfield))p.network_source='informado';touch();}if(t.dataset.photoField){p.photos[Number(t.dataset.photo)][t.dataset.photoField]=t.value;touch();}});
 $('pointEditor').addEventListener('change',run(async ev=>{if(ev.target.id==='photosFile'){try{if(window.FileAttachments)await window.FileAttachments.add('photos',[...ev.target.files]);else await uploadPhotos([...ev.target.files]);}finally{ev.target.value='';}}if(ev.target.dataset.pfield==='number')renderServices();if(ev.target.dataset.pfield==='coordinate'){const p=point(),value=p?.coordinate;if(value){const d=await api('/api/coordinate?q='+encodeURIComponent(value));if(point()===p&&p.coordinate===value){p.lat=d.lat;p.lon=d.lon;p.coordinate=d.utm;ev.target.value=d.utm;touch();}}}}));
 $('pointEditor').addEventListener('click',run(async ev=>{const el=ev.target.closest('button'),p=point();if(!el||!p)return;if(el.id==='uploadPhotos')$('photosFile').click();if(el.id==='lookupPoint')await lookupPoint();if(el.id==='removePoint'){if(S.services.some(s=>s.point_id===p.id)||b.conductors.some(c=>c.from_point===p.id||c.to_point===p.id))throw Error('Reatribua ou remova os serviços e trechos deste ponto antes de excluí-lo.');if(confirm('Excluir o ponto '+p.number+' do rascunho?')){b.points=b.points.filter(q=>q.id!==p.id);delete b.point_drafts[p.id];if(S.editor?.point_id===p.id){S.editor=null;S.selected=null;S.editing=-1;}active='';if(b.points[0])await selectPoint(b.points[0].id);touch();renderPoints();renderServices();}}if(el.id==='pointUp'||el.id==='pointDown'){const i=b.points.indexOf(p),j=i+(el.id==='pointUp'?-1:1);if(j>=0&&j<b.points.length){[b.points[i],b.points[j]]=[b.points[j],b.points[i]];touch();renderPoints();}}if(el.dataset.photoRemove!==undefined){if(confirm('Remover esta foto do ponto?')){p.photos.splice(Number(el.dataset.photoRemove),1);touch();renderPoints();}}for(const [attr,offset] of [['photoUp',-1],['photoDown',1]])if(el.dataset[attr]!==undefined){const i=Number(el.dataset[attr]),j=i+offset;if(j>=0&&j<p.photos.length){[p.photos[i],p.photos[j]]=[p.photos[j],p.photos[i]];touch();renderPoints();}}}));
 $('previewBook').onclick=run(preview);$('previewMaterials').onclick=run(()=>previewReport('/materials-report'));$('exportMaterials').onclick=()=>{if(S.lastSaved)window.open('/materials-report?id='+encodeURIComponent(S.lastSaved.id),'_blank','noopener');};$('formsPreview').onclick=run(preview);$('exportBook').onclick=()=>{if(S.lastSaved)window.open('/book?id='+encodeURIComponent(S.lastSaved.id),'_blank','noopener');};
 $('uploadCroqui').onclick=()=>$('croquiFile').click();$('croquiFile').onchange=run(async ev=>{const files=[...ev.target.files];if(!files.length)return;try{if(window.FileAttachments)await window.FileAttachments.add('croqui',files);else await importCroqui(files);}finally{ev.target.value='';}});
 $('repairCroqui').onclick=()=>$('repairCroquiFile').click();$('repairCroquiFile').onchange=run(async ev=>{const file=ev.target.files[0];if(!file)return;try{await repairCroqui(file);}finally{ev.target.value='';}});
 $('retryCroqui').onclick=()=>renderCroqui();$('testRepository').onclick=testRepository;
 $('croquiPrevious').onclick=run(()=>selectCroqui(activeCroqui-1));$('croquiNext').onclick=run(()=>selectCroqui(activeCroqui+1));$('croquiPage').onchange=run(ev=>selectCroqui(Number(ev.target.value)));$('saveCroquiPdf').onclick=run(exportCroqui);
 $('croquiPreview').onclick=run(async ev=>{if(ev.target.id==='removeCroqui'&&!uploading&&!croquiSwitching&&confirm('Remover esta página do croqui? As demais páginas serão mantidas.')){await window.Drawing.flush({allowMissing:true});b.croqui_pages.splice(activeCroqui,1);activeCroqui=Math.max(0,Math.min(activeCroqui,b.croqui_pages.length-1));pageAliases();touch();renderCroqui();}});
 $('croquiCaption').oninput=()=>{if(currentCroqui()?.croqui){currentCroqui().croqui.caption=$('croquiCaption').value;pageAliases();touch();}};
 $('noConductors').onchange=ev=>{if(ev.target.checked&&b.conductors.length){ev.target.checked=false;toast('Remova os trechos antes de marcar sem movimentação.',true);return;}b.no_conductors=ev.target.checked;touch();renderConductors();};$('addConductor').onclick=run(addConductor);$('estimateLength').onclick=run(estimate);$('conductorRows').onclick=run(async ev=>{const el=ev.target.closest('button');if(!el)return;if(el.dataset.editConductor!==undefined)editConductor(Number(el.dataset.editConductor));if(el.dataset.removeConductor!==undefined&&confirm('Remover este trecho?')){b.conductors.splice(Number(el.dataset.removeConductor),1);editingConductor=-1;$('addConductor').textContent='Adicionar trecho';touch();await checkBook();renderConductors();}});
 $('formsSubmitted').onchange=ev=>{b.forms_submitted=ev.target.checked;touch(true);};$('formsNote').oninput=ev=>{b.forms_note=ev.target.value;touch(true);};$('saveForms').onclick=run(async()=>{if(!b.forms_submitted)throw Error('Preencha o formulário externo e marque a confirmação de envio.');keepForms=true;try{await saveJob('fechado');}finally{keepForms=false;}});$('copyForms').onclick=run(copySummary);$('saveSettings').onclick=run(saveSettings);
 $('checkUpdate').onclick=run(async()=>{
  $('updateResult').textContent='Consultando a versão disponível no GitHub…';$('checkUpdate').disabled=true;
  try{
   const r=await window.Training.checkNotice(true);
   if(!r)return;
   $('applyUpdate').disabled=!r.can_update;
   $('updateResult').textContent=r.error?`${r.error}\n${r.detail||''}`:[r.info||'Repositório e Release encontrados.',r.available
     ?`Versão disponível: ${r.remote_version}\nVersão instalada: ${r.current_version}\nA instalação será automática. Seus dados serão preservados.`
     :`Versão instalada: ${r.current_version}. Versão no repositório: ${r.remote_version}. Não há versão mais nova para instalar.`].join('\n');
  }finally{$('checkUpdate').disabled=false;}
 });
 $('applyUpdate').onclick=run(async()=>{
  if(!confirm('Salvar os dados, baixar a atualização e reiniciar automaticamente o aplicativo?'))return;
  $('applyUpdate').disabled=true;
  $('updateResult').textContent='Salvando dados e baixando a atualização. Aguarde…';
  try{
   await window.SymbolEditor?.flush();
   await flushCroquis();
   await window.Training?.flush(true);
   await window.Training?.pause();
   const r=await api('/api/update-apply',{});
   $('updateResult').textContent=r.message+(r.started?'\nO aplicativo sera reaberto automaticamente. Se necessario, atualize esta guia com F5.':'');
   if(!r.started){window.Training?.resume();$('applyUpdate').disabled=false;}
  }catch(e){window.Training?.resume();$('applyUpdate').disabled=false;$('updateResult').textContent=e.message;throw e;}
 });
 $('mapSearch').onclick=run(mapSearch);$('mapQuery').onkeydown=ev=>{if(ev.key==='Enter')run(mapSearch)();};$('mapActivePoint').onclick=run(async()=>{const p=point();if(!p?.coordinate)throw Error('Selecione um ponto com coordenada.');$('mapQuery').value=p.coordinate;await mapSearch();});['mapBase','mapTD','mapRD','mapPost'].forEach(id=>$(id).onchange=syncMap);$('qfieldMap').onload=syncMap;
 $('mapFullscreen').onclick=run(async()=>{if(document.fullscreenElement)await document.exitFullscreen();else await $('mapContainer').requestFullscreen();});$('mapDistance').onclick=()=>mapWindow().setMeasureMode('distance');$('mapArea').onclick=()=>mapWindow().setMeasureMode('area');$('mapFinish').onclick=()=>mapWindow().finishMeasure();$('mapClear').onclick=()=>mapWindow().clearMeasure();
 $('mapSnapshot').onclick=run(async()=>{const data=mapWindow().exportQFieldSnapshot?.();if(!data)throw Error('Aguarde o mapa carregar.');const ref=await api('/api/media',{name:'Croqui da rede QField.png',data});await window.Drawing.flush();b.croqui_pages=[window.CroquiPages.page(ref,{kind:'image',name:'Croqui da rede QField.png'})];activeCroqui=0;b.croqui_pages[0].croqui.caption='Camadas da base QField. Referência geográfica, sem imagem de satélite.';pageAliases();touch();renderCroqui();toast('Camadas QField incluídas na página de croqui.');});
 document.addEventListener('click',run(async ev=>{const el=ev.target.closest('button');if(!el)return;if(el.dataset.useGeo!==undefined)await useGeo(el.dataset.useGeo);if(el.dataset.mapResult!==undefined){const r=lastGeo.results[Number(el.dataset.mapResult)];mapWindow().flyToEquipment(r.lat,r.lon,r.kind,r.code,17);}}));
 window.addEventListener('message',ev=>{if(ev.origin!==location.origin||ev.source!==mapWindow())return;const data=ev.data;if(data?.type==='bookpoda-measure-result'){$('measureResult').textContent=`Medição: ${fmt(data.data.meters)} m · Área aproximada: ${fmt(data.data.squareMeters)} m² · ${data.data.vertices} vértices`;}if(data?.type==='obra-map-coordinate'){run(async()=>{const r=await api('/api/geo?q='+encodeURIComponent(data.lat+', '+data.lon));geoDisplay(r);})()}});
}
window.Book={init,load,attachPhotos:uploadPhotos,attachCroqui:importCroqui,flushCroquis,selectPoint,activateEditorPoint,renderPointList,summary:()=>b,previewValue:()=>{const {drawing,croqui,point_drafts,...value}=b;return {...value,croqui_pages:b.croqui_pages.map(({drawing,...page})=>page)};},serviceName:bookServiceName,value:()=>{const {croqui,drawing,...value}=b;return cp(value);},activeId:()=>active,autosave,cancelAutosave:()=>{clearTimeout(saveTimer);window.Training?.cancel();},onTab,renderTotals,invalidateForms,afterSave,serviceSelector:id=>`<label class="service-point-label">Ponto da obra<select id="servicePoint">${options(id)}</select></label>`,serviceSelect:(id,i)=>`<select data-service-point="${i}" aria-label="Ponto do serviço ${i+1}">${options(id)}</select>`};
template();
document.querySelector('.drawing-panel').insertAdjacentHTML('beforebegin',`<div class="actions section-spacer"><button id="repairCroqui" class="secondary" hidden>Vincular arquivo original</button><input id="repairCroquiFile" type="file" accept="image/jpeg,image/png,image/webp,application/pdf,.pdf" hidden></div><div id="croquiRecovery" class="notice section-spacer" role="status" hidden><p id="croquiRecoveryMessage"></p><button id="retryCroqui" class="secondary">Tentar carregar novamente</button></div>`);
$('saveSettings').insertAdjacentHTML('afterend',` <button id="testRepository" class="secondary">Testar acesso ao repositório</button><p id="repositoryCheckResult" role="status" class="muted"></p>`);
bind();
})();
