'use strict';
(()=>{
 const node=document.createElement('dialog');node.id='resourceDialog';node.setAttribute('aria-labelledby','resourceTitle');
 node.innerHTML='<div class="resource-heading"><div><h2 id="resourceTitle">Recursos do programa</h2><p>Confira o que está pronto para usar neste computador.</p></div><button type="button" id="resourceClose" aria-label="Fechar">×</button></div><p class="resource-note">A instalação baixa os recursos pela internet para seu usuário. Mantenha o programa aberto. Não é necessário executar como administrador.</p><div id="resourceList"></div><p id="resourceState" role="status" aria-live="polite">Verificando recursos…</p><details id="resourceDetails" hidden><summary>Detalhes da instalação</summary><pre id="resourceLog"></pre></details><button type="button" id="resourceRefresh">Verificar novamente</button>';
 document.body.append(node);
 const button=document.createElement('button');button.type='button';button.id='resourceOpen';button.textContent='Recursos do programa';button.onclick=()=>{node.showModal();refresh();};
 const container=document.querySelector('.sidebar')||document.querySelector('main');container.append(button);
 const $r=id=>document.getElementById(id);const escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 let token='',timer=null,loading=false,latest=null,installing=false;
 const contexts=[];
 for(const [selector,feature,label] of [['#tab-photo-reader .page-heading','ocr','Leitor de fotos'],['#page-book .section-heading','poda','Books de Poda e LF']]){
  const target=document.querySelector(selector);if(!target)continue;
  const panel=document.createElement('section');panel.className='resource-banner';panel.setAttribute('aria-live','polite');panel.innerHTML='<span>Verificando recursos de '+label+'…</span><button type="button" data-resource-open>Ver recursos</button>';target.after(panel);contexts.push({panel,feature,label});
 }
 document.addEventListener('click',ev=>{if(ev.target.closest('[data-resource-open]')){node.showModal();refresh();}});
 $r('resourceClose').onclick=()=>node.close();
 async function request(path,data){const response=await fetch(path,{method:data?'POST':'GET',headers:data?{'Content-Type':'application/json','X-App-Token':token}:{},body:data?JSON.stringify(data):undefined});const result=await response.json();if(!response.ok)throw Error(result.error||'Falha na verificação dos recursos.');return result;}
 function render(data){
  latest=data;const running=data.job.state==='running';installing=running;
  const missing=data.features.filter(f=>!f.ready);button.textContent=running?'Instalando recursos…':missing.length?'Recursos · '+missing.length+' pendência(s)':'Recursos · verificados';button.classList.toggle('resource-pending',missing.length>0);
  $r('resourceList').innerHTML=data.features.map(f=>`<section class="resource-item"><div><strong>${escape(f.name)}</strong><p>${escape(f.detail)}</p><span class="resource-badge ${f.ready?'ready':'missing'}">${f.ready?'Pronto para usar':'Requer atenção'}</span></div>${f.installable?`<button type="button" data-install-resource="${escape(f.id)}" ${running?'disabled':''}>${running&&data.job.feature===f.id?'Instalando…':f.ready?'Verificar / reparar':'Instalar recursos'}</button>`:''}</section>`).join('');
  $r('resourceState').textContent=data.job.message||'Verificação concluída. Instale somente os recursos que deseja utilizar.';
  $r('resourceState').classList.toggle('resource-error',data.job.state==='error');
  $r('resourceDetails').hidden=!data.job.log.length;$r('resourceLog').textContent=data.job.log.join('\n');$r('resourceRefresh').disabled=running;
  for(const {panel,feature,label} of contexts){const f=data.features.find(f=>f.id===feature);panel.hidden=!!f?.ready&&!running;if(panel.hidden)continue;panel.innerHTML=`<span>${escape(running&&data.job.feature===feature?'Instalando recursos. Aguarde para utilizar '+label+'.':label+': '+(f?.detail||'verificação pendente'))}</span><button type="button" data-resource-open>Ver recursos e instalar</button>`;}

 }
 async function refresh(force=false){
  if(loading)return;loading=true;clearTimeout(timer);
  try{const data=await request(force?'/api/resources/check':'/api/resources',force?{}:null);if(data.token)token=data.token;render(data);}
  catch(error){$r('resourceState').textContent=error.message;button.textContent='Recursos · verificar';for(const {panel} of contexts){panel.hidden=false;panel.querySelector('span').textContent='Não foi possível verificar os recursos. Abra Ver recursos e tente novamente.';}}
  finally{loading=false;if(installing)timer=setTimeout(refresh,2000);}
 }
 $r('resourceRefresh').onclick=()=>refresh(!!token);
 $r('resourceList').onclick=async ev=>{const install=ev.target.closest('[data-install-resource]');if(!install||installing||loading)return;installing=true;$r('resourceList').querySelectorAll('button').forEach(b=>b.disabled=true);$r('resourceState').textContent='Iniciando instalação…';
  try{await request('/api/resources/install',{feature:install.dataset.installResource});await refresh();}
  catch(error){installing=false;$r('resourceState').textContent=error.message;$r('resourceList').querySelectorAll('button').forEach(b=>b.disabled=false);}
 };
 document.addEventListener('click',ev=>{const action=ev.target.closest('#readerAnalyze,#generate-pdf');if(!action)return;const id=action.id==='readerAnalyze'?'ocr':'poda';if(installing||!latest?.features.find(f=>f.id===id)?.ready){ev.preventDefault();ev.stopImmediatePropagation();node.showModal();refresh();}},true);
 refresh();
 // Recheck when returning to the reader, without polling engines during photo processing.
 document.addEventListener('click',ev=>{if(ev.target.closest('[data-tab="photo-reader"]')&&!installing)refresh();});
})();
