'use strict';
(() => {
 let lastSuccess='',poll;
 $('automaticStatus').insertAdjacentHTML('afterend','<div id="repositorySyncStatus" class="automatic-status repository-status" role="status">Registros da equipe: aguardando sincronização.</div>');
 $('tab-settings').insertAdjacentHTML('beforeend',`<section class="card padded section-spacer"><h2>Registros da equipe no repositório</h2><p>Envio e recebimento automáticos a cada minuto, enquanto o servidor estiver aberto. Os registros repetidos também participam do padrão.</p><p class="muted">Compartilha responsável, data, mão de obra e materiais com quem tem acesso ao repositório. Fotos, PDF, croqui e dados gerais da obra permanecem no computador.</p><p class="muted">Cada computador precisa de Git instalado e de uma credencial com permissão de escrita no repositório. A pasta dados mantém o histórico e os envios pendentes.</p><button id="syncRecordsNow" class="primary">Sincronizar agora</button><pre id="recordsSyncDetails" class="update-result" role="status"></pre></section>`);
 function show(state){
  const banner=$('repositorySyncStatus'),when=state.last_success?new Date(state.last_success).toLocaleString('pt-BR'):'nenhuma sincronização concluída';
  const message=!state.enabled?'Sincronização desativada nas configurações.':state.running?'Sincronizando registros com a equipe…':state.error?'Envio/recebimento pendente. '+state.error:state.last_success?'Registros da equipe sincronizados · '+when:'Aguardando a primeira sincronização com o repositório.';
  banner.textContent=message;banner.classList.toggle('error',!!state.error&&state.enabled);
  $('recordsSyncDetails').textContent=[message,'Repositório: '+state.repository,'Branch dos registros: '+state.branch,'Última conclusão: '+when,'Enviados no último ciclo: '+state.uploaded+' · Recebidos: '+state.downloaded+(state.pending!==null?' · Envios pendentes: '+state.pending:'')].join('\n');
  $('syncRecordsNow').disabled=state.running||!state.enabled;
  if(state.last_success&&state.last_success!==lastSuccess){lastSuccess=state.last_success;if(!$('tab-profiles').hidden)window.Training?.refreshPatterns().catch(()=>{});}
 }
 async function refresh(){try{show(await api('/api/records-sync'));}catch{$('repositorySyncStatus').textContent='Servidor indisponível; os registros ficam guardados localmente até a próxima conexão.';}}
 function init(){refresh();clearInterval(poll);poll=setInterval(refresh,10000);}
 $('syncRecordsNow').onclick=run(async()=>{await window.Training?.flush();show(await api('/api/records-sync',{}));setTimeout(refresh,1000);});
 window.RecordSyncUI={init,refresh};
})();
