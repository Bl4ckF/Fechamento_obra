const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const handlers={},tabs={'tab-book':{hidden:false},'tab-conductors':{hidden:true}};let owner={points:[{id:'p1'},{id:'p2'}]},active='p1',release,pause=false,modal=false;const calls=[];
const env={window:{addEventListener(){},Book:{summary:()=>owner,activeId:()=>active,attachPhotos:async(files,id)=>{calls.push({files,id});if(pause)await new Promise(r=>release=r);},attachCroqui:async files=>calls.push({files,kind:'croqui'})}},document:{addEventListener:(name,fn)=>handlers[name]=fn,querySelector:s=>s==='dialog[open]'&&modal?{}:null},$:id=>tabs[id],File:class{constructor(parts,name,options){this.name=name;this.type=options.type;}},toast(){},Date};
vm.createContext(env);vm.runInContext(fs.readFileSync(path.join(__dirname,'../web/file-attachments.js'),'utf8'),env);const attachments=env.window.FileAttachments;
(async()=>{
 const image={name:'FOTO.PNG',type:''},pdf={name:'projeto.pdf',type:'application/pdf'};
 await attachments.add('photos',[image]);assert.equal(calls[0].files[0].type,'image/png');assert.equal(calls[0].id,'p1');
 await assert.rejects(attachments.add('photos',[pdf]),/apenas imagens/);await assert.rejects(attachments.add('croqui',[pdf,image]),/um PDF/);
 await attachments.add('croqui',[image,image]);assert.equal(calls.at(-1).files.length,2);
 const file={name:'clipboard.png',type:'image/png'};assert.equal(attachments.filesFrom({files:[file],items:[{kind:'file',getAsFile:()=>file}]}).length,1,'Clipboard files and items must not produce duplicate attachments');
 assert.equal(attachments.filesFrom({files:[],items:[{kind:'file',getAsFile:()=>file}]}).length,1);
 let prevented=false;handlers.paste({clipboardData:{files:[],items:[]},preventDefault(){prevented=true;}});assert.equal(prevented,false,'Normal text copy/paste remains native');
 pause=true;const first=attachments.add('photos',[image]);for(let i=0;i<5;i++)await Promise.resolve();const next=attachments.add('photos',[image]);active='p2';release();pause=false;await first;await next;assert.equal(calls.at(-1).id,'p1','Queued files belong to the point chosen at the time of paste/drop');
 pause=true;const pending=attachments.add('photos',[image]);for(let i=0;i<5;i++)await Promise.resolve();const stale=attachments.add('photos',[image]);owner={points:[{id:'p2'}]};release();pause=false;await pending;await assert.rejects(stale,/obra mudou/);
 active='missing';await assert.rejects(attachments.add('photos',[image]),/selecione um ponto/);
 console.log('OK: anexos por contexto, MIME por extensão, arquivos repetidos, colagem de texto, fila e proteção ao trocar de obra/ponto.');
})().catch(e=>{console.error(e);process.exitCode=1;});
