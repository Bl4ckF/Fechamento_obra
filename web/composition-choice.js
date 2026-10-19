'use strict';
(() => {
 const dialog=document.createElement('dialog');dialog.id='compositionChoice';dialog.className='composition-choice-dialog';dialog.setAttribute('aria-labelledby','compositionTitle');
 dialog.innerHTML=`<div class="dialog-heading"><div><p id="compositionStep" class="eyebrow">ETAPA 1 DE 2</p><h2 id="compositionTitle">Os materiais são de trafo ou estrutura?</h2></div><button id="cancelComposition" class="secondary">Cancelar</button></div><p id="compositionLabor" class="muted"></p>
 <div id="compositionType" class="composition-types"><button data-composition-kind="transformer"><strong>Trafo / transformador</strong><span>Fases, tensão, potência e configuração do trafo</span></button><button data-composition-kind="structure"><strong>Estrutura</strong><span>Estrutura da rede e tipo de poste</span></button></div>
 <section id="compositionConfiguration" hidden><p id="compositionHint" class="muted"></p><div id="compositionFilters" class="composition-filters"></div><label id="compositionBaseLabel">Configuração<select id="compositionBase"></select></label><label id="compositionContextLabel">Complemento / modelo exato (opcional)<input id="compositionContext" maxlength="160" placeholder="Ex.: 75 kVA · 220/127 V"></label><label id="compositionModeLabel">Movimentação dos materiais<select id="compositionMode"></select></label><p id="compositionMovement" class="notice"></p><div class="actions section-spacer"><button id="backComposition" class="secondary">← Trafo ou estrutura</button><button id="applyComposition" class="primary" disabled>Carregar materiais e continuar</button></div></section>
 <button id="manualComposition" class="text-button section-spacer">Preencher materiais manualmente / serviço sem materiais</button>`;
 document.body.appendChild(dialog);
 const el=id=>document.getElementById(id);let resolveChoice=null,labor=null,kind='',filters={},chosen='';
 const fields=()=>kind==='structure'?[['structure','Estrutura'],['pole','Tipo de poste']]:baseFields.transformer;
 const defaultMode=()=>labor.operation==='RETIRAR'?'desativado':labor.operation==='INSTALAR'?'instalado':kind==='transformer'?'planilha':'instalado';
 function finish(value){const done=resolveChoice;resolveChoice=null;dialog.close();done?.(value);}
 function renderOptions(){
  let candidates=S.bases.filter(b=>b.kind===kind),html='';
  for(const [key,label] of fields()){
   const values=[...new Set(candidates.map(b=>b.params[key]))].sort((a,b)=>a.localeCompare(b,'pt-BR',{numeric:true}));
   if(filters[key]&&!values.includes(filters[key]))delete filters[key];
   html+=`<label>${esc(label)}<select data-composition-filter="${key}"><option value="">Todas as opções</option>${values.map(v=>`<option value="${esc(v)}" ${filters[key]===v?'selected':''}>${esc(v)}</option>`).join('')}</select></label>`;
   if(filters[key])candidates=candidates.filter(b=>b.params[key]===filters[key]);
  }
  if(!candidates.some(b=>b.id===chosen))chosen=candidates.length===1?candidates[0].id:'';
  el('compositionFilters').innerHTML=html;
  el('compositionBase').innerHTML=`<option value="">Selecione entre ${candidates.length} configurações…</option>`+candidates.map(b=>`<option value="${b.id}" ${chosen===b.id?'selected':''}>${esc(b.title)}</option>`).join('');
  el('applyComposition').disabled=!chosen;
 }
 function setKind(value){
  kind=value;filters={};chosen='';el('compositionType').hidden=true;el('compositionConfiguration').hidden=false;el('compositionStep').textContent='ETAPA 2 DE 2';el('compositionTitle').textContent=kind==='transformer'?'Qual trafo será usado?':'Qual estrutura será usada?';
  el('compositionHint').textContent=kind==='transformer'?'Escolha as características do trafo ou selecione diretamente a configuração completa.':'Escolha a estrutura e o tipo de poste ou selecione diretamente a configuração completa.';
  el('compositionContext').value='';el('compositionContext').placeholder=kind==='transformer'?'Ex.: 75 kVA · 220/127 V':'Ex.: configuração especial';
  el('compositionModeLabel').hidden=labor.operation!=='EXECUTAR';const mode=defaultMode();
  el('compositionMode').innerHTML=(kind==='transformer'?'<option value="planilha">Colunas INST. e DESAT. da planilha</option>':'')+'<option value="instalado">Instalados</option><option value="desativado">Desativados</option>';el('compositionMode').value=mode;
  el('compositionMovement').textContent=labor.operation==='INSTALAR'?'Instalação: serão carregados os materiais instalados.':labor.operation==='RETIRAR'?'Retirada: serão carregados os materiais desativados.':'Confira a movimentação dos materiais deste serviço.';
  renderOptions();el('compositionFilters').querySelector('select')?.focus();
 }
 el('compositionType').onclick=event=>{const button=event.target.closest('[data-composition-kind]');if(button)setKind(button.dataset.compositionKind);};
 el('compositionFilters').onchange=event=>{const key=event.target.dataset.compositionFilter;if(!key)return;filters[key]=event.target.value;const keys=fields().map(f=>f[0]);keys.slice(keys.indexOf(key)+1).forEach(k=>delete filters[k]);chosen='';renderOptions();el('compositionFilters').querySelector(`[data-composition-filter="${key}"]`)?.focus();};
 el('compositionBase').onchange=event=>{chosen=event.target.value;const base=S.bases.find(b=>b.id===chosen);if(base)filters={...base.params};renderOptions();};
 el('applyComposition').onclick=()=>{if(!chosen)return;finish({kind,base_id:chosen,mode:el('compositionMode').value,context:el('compositionContext').value.trim()});};
 el('backComposition').onclick=()=>{el('compositionType').hidden=false;el('compositionConfiguration').hidden=true;el('compositionStep').textContent='ETAPA 1 DE 2';el('compositionTitle').textContent='Os materiais são de trafo ou estrutura?';};
 el('cancelComposition').onclick=()=>finish(null);el('manualComposition').onclick=()=>finish({manual:true});dialog.addEventListener('cancel',event=>{event.preventDefault();finish(null);});
 window.CompositionChoice={choose(selected){if(resolveChoice)return Promise.resolve(null);labor=selected;el('compositionLabor').textContent=(labor.code?labor.code+' · ':'')+labor.description;el('backComposition').onclick();dialog.showModal();return new Promise(resolve=>resolveChoice=resolve);}};
})();
