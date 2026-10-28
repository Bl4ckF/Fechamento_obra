'use strict';
// Adapta exportações dos módulos web ao armazenamento da obra, sem downloads.
(()=>{
 if(parent===window)return;
 const operation=location.pathname.split('/')[2];
 if(!/^[a-z]+craft$/.test(operation))return;
 const send=message=>parent.postMessage({...message,type:operation+':'+message.type},location.origin);
 window.addEventListener('error',event=>send({type:'failed',error:event.message||'Falha ao carregar a operação.'}));
 window.addEventListener('unhandledrejection',event=>send({type:'failed',error:String(event.reason?.message||event.reason||'Falha ao iniciar a operação.')}));
 if(['pdfcraft','cadcraft','gridcraft'].includes(operation))return;
 let pendingFile=null;
 const originalInputClick=HTMLInputElement.prototype.click;
 HTMLInputElement.prototype.click=function(){
  if(this.type==='file'&&pendingFile){
   const transfer=new DataTransfer();transfer.items.add(pendingFile);this.files=transfer.files;pendingFile=null;
   this.dispatchEvent(new Event('input',{bubbles:true}));this.dispatchEvent(new Event('change',{bubbles:true}));return;
  }
  return originalInputClick.call(this);
 };
 window.addEventListener('message',event=>{
  if(event.origin!==location.origin||event.source!==parent||event.data?.type!==operation+':open')return;
  const {name,bytes}=event.data;
  if(typeof name!=='string'||!(bytes instanceof ArrayBuffer)||bytes.byteLength>50_000_000)return;
  pendingFile=new File([bytes],name);send({type:'open-pending'});
 });
 const originalClick=HTMLAnchorElement.prototype.click;
 const saving=new Set();
 async function save(anchor){
  const url=anchor.href;if(!url||saving.has(url))return;
  saving.add(url);send({type:'dirty',dirty:true});
  try{
   const parsed=new URL(url,location.href);
   if(!['blob:','data:'].includes(parsed.protocol)&&parsed.origin!==location.origin)throw Error('Origem do documento inválida.');
   const response=await fetch(url);if(!response.ok)throw Error('Não foi possível ler o documento.');
   const bytes=await response.arrayBuffer();
   parent.postMessage({type:operation+':save',name:anchor.download||'documento',bytes},location.origin,[bytes]);
  }catch(error){send({type:'failed',error:error.message});}
  finally{saving.delete(url);}
 }
 HTMLAnchorElement.prototype.click=function(){if(this.hasAttribute('download')){void save(this);return;}return originalClick.call(this);};
 document.addEventListener('click',event=>{const anchor=event.target.closest?.('a[download]');if(anchor){event.preventDefault();void save(anchor);}},true);
 send({type:'ready'});
})();
