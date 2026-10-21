'use strict';
(() => {
 let lastEvent=0;
 async function report(category,file='',line=0){
  if(Date.now()-lastEvent<10000||typeof api!=='function')return;
  lastEvent=Date.now();
  try{await api('/api/diagnostics-event',{category,file,line});}catch{/* A coleta não interfere na edição. */}
 }
 window.addEventListener('error',event=>{
  let file='';try{const url=new URL(event.filename);if(url.origin===location.origin)file=url.pathname.split('/').pop()||'';}catch{}
  if(!/^[a-zA-Z0-9_.-]{1,80}\.m?js$/.test(file))file='';
  void report('javascript_error',file,Number.isInteger(event.lineno)?event.lineno:0);
 });
 window.addEventListener('unhandledrejection',()=>void report('unhandled_rejection'));
 const button=document.getElementById('downloadDiagnostics');
 button?.addEventListener('click',async()=>{
  button.disabled=true;
  try{
   const data=await api('/api/diagnostics',{}),blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),link=document.createElement('a');
   link.href=url;link.download='diagnostico_fechamento_v'+data.version+'.json';document.body.appendChild(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),10000);
  }catch(error){if(typeof toast==='function')toast(error.message);}
  finally{button.disabled=false;}
 });
})();
