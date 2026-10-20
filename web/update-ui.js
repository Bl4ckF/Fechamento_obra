'use strict';
(() => {
 const stateKey='engelmig-update-view',readKey='engelmig-update-read';
 let current='',notice=null,installing=false,checking=false,oldInstance='',restored=false;
 const ui=id=>document.getElementById(id),delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
 function message(text,error=false){ui('updateDialogMessage').textContent=text;ui('updateDialogMessage').classList.toggle('update-error',error);}
 function paint(){
  const available=!!notice?.available,key=String(notice?.key||notice?.remote_version||'');
  let unread=false;try{unread=available&&sessionStorage.getItem(readKey)!==key;}catch{unread=available;}
  const bell=ui('updateBell');bell.classList.toggle('has-update',available);bell.classList.toggle('is-unread',unread);ui('updateBellBadge').hidden=!available;
  const label=available?'Atualização disponível: versão '+notice.remote_version:'Atualizações do programa';bell.title=label;bell.setAttribute('aria-label',label);
  ui('updateInstalledVersion').textContent=current||'…';ui('updateAvailableVersion').textContent=notice?.remote_version||'Aguardando consulta';
  ui('updateDialogInstall').disabled=installing||checking||!notice?.can_update;
  ui('updateDialogCheck').disabled=installing||checking;ui('updateDialogClose').disabled=installing;
  ui('updateProgress').hidden=!installing;
 }
 function display(data){
  if(data.current_version)current=data.current_version;
  if(!data.error)notice=data;else if(!notice)notice=data;
  paint();
  if(!installing){message(data.error?[data.error,data.detail].filter(Boolean).join(' '):data.available?'Uma nova versão está disponível. Seus registros serão preservados.':'O programa está atualizado.',!!data.error);}
 }
 async function check(){
  if(checking||installing)return;checking=true;message('Verificando se há uma nova versão…');paint();
  try{const result=await window.Training.checkNotice(true);if(!result)message('Não foi possível consultar a atualização. Tente novamente.',true);}
  finally{checking=false;paint();}
 }
 function acknowledge(){if(!notice?.available)return;try{sessionStorage.setItem(readKey,String(notice.key||notice.remote_version));}catch{}paint();}
 async function open(force=false){
  if(!ui('updateDialog').open)ui('updateDialog').showModal();acknowledge();if(!notice||force)await check();acknowledge();
 }
 function viewState(){return {tab:document.querySelector('.nav.active')?.dataset.tab||'book',point:window.Book?.activeId(),croqui:window.Book?.viewState?.().croqui||0,scroll:window.scrollY,preview:!!ui('liveBookPreview')?.open,version:current};}
 function progress(step,text){document.querySelectorAll('#updateProgress li').forEach((node,index)=>{node.classList.toggle('active',index===step);node.classList.toggle('complete',index<step);});message(text);}
 async function health(){const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),2200);try{const response=await fetch('/api/health',{cache:'no-store',signal:controller.signal});if(!response.ok)throw Error('Aguardando o programa.');return await response.json();}finally{clearTimeout(timer);}}
 async function waitRestart(expected){
  let disconnected=false;const deadline=Date.now()+180000;
  while(Date.now()<deadline){
   await delay(1200);
   try{
    const server=await health();
    if(server.app!=='engelmig-fechamento-v1')continue;
    if(server.version===expected||(oldInstance&&server.instance_id&&server.instance_id!==oldInstance)){
     try{const result=await(await fetch('/api/update-status',{cache:'no-store'})).json();if(result.state==='error')sessionStorage.setItem('engelmig-update-error',result.message);}catch{}
     progress(3,'Programa iniciado. Reabrindo esta mesma aba…');location.reload();return;
    }
    if(disconnected)progress(2,'Aguardando a versão atualizada iniciar…');
   }catch{disconnected=true;progress(2,'Instalando a atualização e reiniciando o programa…');}
  }
  installing=false;window.Training?.resume();paint();message('O programa ainda não respondeu. Aguarde um pouco e clique em Verificar novamente. Se necessário, inicie VERIFICAR_E_INICIAR.bat; esta aba pode ser mantida aberta.',true);
 }
 async function install(){
  if(installing||!notice?.can_update)return;
  installing=true;paint();progress(0,'Salvando o trabalho antes de atualizar…');
  try{
   await window.SymbolEditor?.flush();await window.Book?.flushCroquis();await window.Training?.flush();
   persist();sessionStorage.setItem(stateKey,JSON.stringify(viewState()));
   try{oldInstance=(await health()).instance_id||'';}catch{}
   await window.Training?.pause();progress(1,'Baixando a nova versão. Mantenha esta aba aberta…');
   const result=await api('/api/update-apply',{});
   if(!result.started){installing=false;window.Training?.resume();sessionStorage.removeItem(stateKey);paint();message(result.message||'Não há atualização para instalar.');return;}
   progress(2,'Instalando e reiniciando automaticamente…');await waitRestart(result.remote_version||notice.remote_version);
  }catch(error){installing=false;window.Training?.resume();sessionStorage.removeItem(stateKey);paint();message(error.message,true);}
 }
 async function restore(data){
  current=data.version||current;paint();if(restored)return;restored=true;
  let view;try{view=JSON.parse(sessionStorage.getItem(stateKey)||'null');}catch{}
  if(view){
   await window.Book?.restoreView?.(view);
   showTab(['work','book','conductors','forms','map','history','catalog','profiles','settings','help'].includes(view.tab)?view.tab:'book');
   if(ui('liveBookPreview'))ui('liveBookPreview').open=!!view.preview;
   requestAnimationFrame(()=>requestAnimationFrame(()=>window.scrollTo(0,Number(view.scroll)||0)));
   sessionStorage.removeItem(stateKey);
  }
  const error=sessionStorage.getItem('engelmig-update-error');if(error){sessionStorage.removeItem('engelmig-update-error');await open(false);message('Não foi possível concluir a atualização: '+error,true);}
 }
 function create(){
  const header=document.querySelector('.shell>header');
  header.insertAdjacentHTML('beforeend',`<button id="updateBell" class="update-bell" title="Atualizações do programa" aria-label="Atualizações do programa" aria-haspopup="dialog" aria-controls="updateDialog"><svg class="update-bell-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9Z"/><path d="M10 21h4M12 2V1"/></svg><span id="updateBellBadge" class="update-bell-badge" hidden>1</span></button>`);
  document.body.insertAdjacentHTML('beforeend',`<dialog id="updateDialog" class="update-dialog" aria-labelledby="updateDialogTitle"><div class="dialog-heading"><div><p class="eyebrow">ATUALIZAÇÕES</p><h2 id="updateDialogTitle">Atualização do programa</h2></div><button id="updateDialogClose" class="secondary">Fechar</button></div><div class="update-versions"><div><span>Versão instalada</span><strong id="updateInstalledVersion">…</strong></div><div><span>Versão disponível</span><strong id="updateAvailableVersion">Aguardando consulta</strong></div></div><p id="updateDialogMessage" role="status" aria-live="polite">Verifique se há uma nova versão.</p><ol id="updateProgress" class="update-progress" hidden><li>Salvar trabalho</li><li>Baixar atualização</li><li>Instalar e reiniciar</li><li>Continuar nesta aba</li></ol><p class="muted">A instalação preserva seus registros e mantém esta mesma aba aberta.</p><div class="actions"><button id="updateDialogCheck" class="secondary">Verificar novamente</button><button id="updateDialogInstall" class="primary" disabled>Atualizar agora</button></div></dialog>`);
  ui('updateBell').onclick=()=>open();ui('updateDialogCheck').onclick=check;ui('updateDialogInstall').onclick=install;ui('updateDialogClose').onclick=()=>ui('updateDialog').close();
  ui('updateDialog').addEventListener('cancel',event=>{if(installing)event.preventDefault();});
 }
 create();window.UpdateUI={display,open,restore,clear:()=>{notice=null;paint();message('Verifique as atualizações para o repositório configurado.');}};
})();
