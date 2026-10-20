// Integração de navegação, autosalvamento e exportação por página, sem navegador.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const nodes=new Map();
class Element{
 constructor(){this.value='';this.checked=false;this.disabled=false;this.hidden=false;this.style={};this.dataset={};this.classList={toggle(){}};}
 insertAdjacentHTML(where,html){for(const m of html.matchAll(/\bid="([^"]+)"/g))node(m[1]);}
 set innerHTML(value){this.html=value;this.insertAdjacentHTML('',value);}get innerHTML(){return this.html;}
 querySelector(s){return node(s);}querySelectorAll(){return [];}addEventListener(name,fn){(this.events??={})[name]=fn;}
}
const node=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);};
let callbacks,currentDoc,uploadResolve,uploadDelay=false,failFlush=false,pending=null,saved=0,downloaded=null;
const env={window:{addEventListener(){}},document:{getElementById:node,querySelector:node,querySelectorAll:()=>[],addEventListener(){}},$:node,
 S:{services:[],bases:[],labor:{},result:{services:[]}},crypto:require('node:crypto').webcrypto,
 cp:x=>JSON.parse(JSON.stringify(x)),esc:x=>String(x??''),fmt:String,dirty(){saved++;},run:fn=>(...args)=>fn(...args),confirm:()=>true,toast(){},renderServices(){},renderLabor(){},loadSuggestions:async()=>{},prepareBaseControls(){},renderEditor(){},persist(){saved++;},setTimeout:()=>1,clearTimeout(){},location:{origin:'http://local'},
 api:async(url,data)=>{if(url==='/api/media-check')return {missing:[]};if(url==='/api/media'){if(uploadDelay)await new Promise(resolve=>uploadResolve=resolve);return {ref:'f'.repeat(64)+'.png',name:data.name};}return {};},
};
env.window.Drawing={init:opts=>callbacks=opts,load:doc=>{currentDoc=doc;},flush:async()=>{if(failFlush)throw Error('Falha de salvamento');if(pending)await pending;}};
env.window.CroquiExport={download:async(pages,order)=>{downloaded={pages,order};}};
vm.createContext(env);for(const name of ['croqui-pages.js','book.js'])vm.runInContext(fs.readFileSync(path.join(__dirname,'../web',name),'utf8'),env);
const book=env.window.Book,pages=env.window.CroquiPages;
(async()=>{
 book.init({});book.load({croqui:{ref:'a'.repeat(64)+'.png',caption:'Antigo'},drawing:{version:1,objects:[]}});assert.equal(book.value().croqui_pages.length,1);assert.equal(node('croquiCaption').value,'Antigo');
 const one=pages.page({ref:'a'.repeat(64)+'.png'},{kind:'pdf',page:1}),two=pages.page({ref:'b'.repeat(64)+'.png'},{kind:'pdf',page:4});
 book.load({croqui_pages:[one,two]});assert.equal(currentDoc.background_source.page,1);
 const changed=JSON.parse(JSON.stringify(currentDoc));changed.objects=[{id:'pdf_0',type:'text',pdf_text_id:'pdf_0',text:'Texto movido',x1:200,y1:320}];callbacks.onChange(changed);
 assert.equal(book.value().croqui_pages[0].image_pending,true,'The draft records pending PNG generation');
 node('croquiCaption').value='Observações da primeira';node('croquiCaption').oninput();
 uploadDelay=true;pending=callbacks.onImage('data:image/png;base64,AA',JSON.stringify(changed));const switchPage=node('croquiNext').onclick();assert.equal(currentDoc.background_source.page,1,'Switch waits for image upload');
 uploadResolve();await pending;pending=null;await switchPage;uploadDelay=false;
 assert.equal(currentDoc.background_source.page,4);assert.equal(book.value().croqui_pages[0].croqui.ref,'f'.repeat(64)+'.png');assert.equal(book.value().croqui_pages[0].croqui.caption,'Observações da primeira');assert.equal(book.value().croqui_pages[1].drawing.objects.length,0);
 assert.equal(book.value().croqui_pages[0].image_pending,undefined);
 node('croquiCaption').value='Segunda folha';node('croquiCaption').oninput();failFlush=true;await assert.rejects(node('croquiPrevious').onclick(),/Falha/);assert.equal(currentDoc.background_source.page,4);failFlush=false;
 await node('croquiPrevious').onclick();assert.equal(currentDoc.objects[0].x1,200);assert.equal(node('croquiCaption').value,'Observações da primeira');
 node('workOrder').value='OS-123';await node('saveCroquiPdf').onclick();assert.equal(downloaded.pages.length,2);assert.equal(downloaded.pages[0].drawing.objects[0].y1,320);assert.equal(downloaded.pages[1].croqui.caption,'Segunda folha');assert.equal(downloaded.order,'OS-123');
 const persistent=book.value();assert.equal(persistent.croqui,undefined,'No duplicate page geometry in drafts');book.load(null);book.load(persistent);assert.equal(currentDoc.objects[0].text,'Texto movido');
 // An upload from the previous work must not replace the newly opened croqui.
 uploadDelay=true;const previous=callbacks.onImage('data:image/png;base64,BB',JSON.stringify(currentDoc));book.load({croqui_pages:[two]});uploadResolve();await previous;assert.equal(book.value().croqui_pages[0].croqui.ref,'b'.repeat(64)+'.png');
 uploadDelay=false;await node('croquiPreview').onclick({target:{id:'removeCroqui'}});assert.equal(book.value().croqui_pages.length,0);assert.equal(currentDoc,null);assert.ok(saved>0);
 // Uma restauração pode conter páginas ainda não renderizadas, inclusive fora da página ativa.
 book.load({croqui_pages:[one,{...two,image_pending:true}]});let flushed=[];
 env.window.Drawing.flush=async()=>{const page=callbacks.getPages().find(p=>p.id===callbacks.getPageId());flushed.push(page.id);if(page.image_pending)await callbacks.onImage('data:image/png;base64,CC',JSON.stringify(page.drawing),page.drawing);};
 await book.flushCroquis();assert.deepEqual(flushed,[one.id,two.id]);assert.equal(currentDoc.background_source.page,1);assert.equal(book.value().croqui_pages[1].image_pending,undefined);assert.equal(book.value().croqui_pages[1].croqui.ref,'f'.repeat(64)+'.png');
 book.load({points:[{id:'p1',number:'1',photos:[]},{id:'p2',number:'2',photos:[]}],croqui_pages:[one]});
 env.S.selected='laborA';env.S.editor={entry_id:'entryA',labor_id:'laborA',point_id:'p1',quantity:'2',materials:[{coefficient:'3'}]};env.S.editorTouched=true;env.S.editing=-1;
 await book.selectPoint('p2');assert.equal(book.activeId(),'p2');assert.equal(env.S.editor,null);
 assert.equal(book.value().point_drafts.p1.editor.quantity,'2');
 env.S.selected='laborB';env.S.editor={entry_id:'entryB',labor_id:'laborB',point_id:'p2',quantity:'4',materials:[]};env.S.editing=-1;
 await book.selectPoint('p1');assert.equal(env.S.editor.entry_id,'entryA');assert.equal(env.S.editor.materials[0].coefficient,'3');
 const stash=book.value();assert.equal(stash.point_drafts.p2.editor.quantity,'4');
 const lightweight=book.previewValue();assert.equal(lightweight.point_drafts,undefined);assert.equal(lightweight.croqui_pages[0].drawing,undefined);assert.ok(book.value().croqui_pages[0].drawing);
 book.load(stash);await book.selectPoint('p2');assert.equal(env.S.editor.entry_id,'entryB');assert.equal(env.S.editor.quantity,'4');
 // Excluir um ponto remove apenas seus vínculos e não permite que rascunhos o recriem.
 env.recalculate=async()=>{};env.closeLaborEditor=()=>{env.S.editor=null;env.S.selected=null;env.S.editing=-1;};
 const points=[{id:'p1',number:'1',photos:[{ref:'a'.repeat(64)+'.png'}]},{id:'p2',number:'2',photos:[]}];
 env.S.services=[{entry_id:'e1',point_id:'p1'},{entry_id:'e2',point_id:'p2'}];env.S.editor=null;env.S.editing=-1;
 book.load({points,conductors:[{from_point:'p1',to_point:'p2'}],point_drafts:{p1:{editor:{entry_id:'e1',point_id:'p1'},editing:0},p2:{editor:{entry_id:'e2',point_id:'p2'},selected:'laborB',editing:1}}});
 env.confirm=()=>false;await book.removePoint();assert.equal(book.value().points.length,2);assert.equal(env.S.services.length,2);
 env.confirm=()=>true;await book.removePoint();assert.deepEqual(Array.from(book.value().points,p=>p.id),['p2']);assert.equal(book.value().conductors.length,0);assert.equal(env.S.services[0].entry_id,'e2');assert.equal(env.S.editor.entry_id,'e2');assert.equal(env.S.editing,0);assert.equal(book.value().point_drafts.p1,undefined);
 await book.removePoint();assert.equal(book.value().points.length,0);assert.equal(env.S.services.length,0);assert.equal(env.S.editor,null);
 console.log('OK: migração, páginas independentes, troca após salvamento, falha de gravação, exportação e proteção contra resposta atrasada de outra obra.');
})().catch(error=>{console.error(error);process.exitCode=1;});
