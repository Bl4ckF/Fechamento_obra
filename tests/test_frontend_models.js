/* Exercita o documento de croqui e a fila de autosalvamento sem navegador. */
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const web=path.join(__dirname,'../web');
const drawing={window:{}};vm.createContext(drawing);vm.runInContext(fs.readFileSync(path.join(web,'pdf-lines.js'),'utf8'),drawing);vm.runInContext(fs.readFileSync(path.join(web,'drawing.js'),'utf8'),drawing);
const Model=drawing.window.Drawing.DrawingModel,model=new Model(),doc=JSON.parse(JSON.stringify(model.doc));
doc.objects.push({id:'line',type:'line',x1:10,y1:20,x2:200,y2:300,color:'#123456',width:8,dash:'dashed',arrow:'both'});
model.commit(doc);doc.objects[0].color='#ffffff';assert.equal(model.doc.objects[0].color,'#123456');
assert.equal(model.undo(),true);assert.equal(model.doc.objects.length,0);assert.equal(model.redo(),true);assert.equal(model.doc.objects[0].dash,'dashed');
assert.equal(model.doc.objects[0].arrow,'both');assert.equal(drawing.window.Drawing.bounds(model.doc.objects[0]).w,190);
const unchanged=model.doc.objects[0];
model.commit({...model.doc,objects:[unchanged,{id:'text',type:'text',text:'ANTES',x1:50,y1:60}]});const before=model.doc;
const edited={...before.objects[1],text:'DEPOIS'};model.commit({...before,objects:[unchanged,edited]});edited.text='MUTACAO EXTERNA';
assert.equal(model.doc.objects[0],unchanged,'Unchanged geometry is shared instead of recopied for each keystroke');assert.equal(model.doc.objects[1].text,'DEPOIS');assert.equal(before.objects[1].text,'ANTES');
model.undo();assert.equal(model.doc.objects[1].text,'ANTES');model.redo();assert.equal(model.doc.objects[1].text,'DEPOIS');

const elements=new Map();
function element(id){if(!elements.has(id))elements.set(id,{value:'',textContent:'',hidden:false,disabled:false,innerHTML:'',classList:{toggle(){}},querySelector(selector){return element(id+' '+selector);},insertAdjacentHTML(){},addEventListener(){},click(){}});return elements.get(id);}
let pendingResolve,calls=[],currentName='Ana';
const environment={window:{addEventListener(){}},document:{getElementById:element,querySelector:element},$:element,
 crypto:require('node:crypto').webcrypto,
 S:{token:'test',services:[],selected:null,editor:null,editing:-1,editorTouched:false},
 meta:()=>({draft_id:'work',work_order:'QA',responsible:currentName,book:{points:[]}}),
 cp:x=>JSON.parse(JSON.stringify(x)),esc:String,norm:s=>String(s||'').toUpperCase(),fmt:String,opBadge:String,
 run:fn=>(...args)=>fn(...args),setTimeout:()=>1,clearTimeout(){},setInterval:()=>1,clearInterval(){},
 api:async(url,data)=>{calls.push({url,data});if(calls.length===1)await new Promise(resolve=>pendingResolve=resolve);return {updated_at:'2026-10-14T20:00:00Z',learning:{changed:1,pending:[]}};},
 sessionStorage:{getItem:()=>null,setItem(){}},localStorage:{setItem(){}},location:{},Blob,Date,
};
vm.createContext(environment);vm.runInContext(fs.readFileSync(path.join(web,'learning.js'),'utf8'),environment);
(async()=>{
 environment.window.Training.init({patterns:[]});
 const first=environment.window.Training.flush();assert.equal(calls.length,1);
 currentName='Bruno';const second=environment.window.Training.flush();assert.equal(calls.length,1);
 pendingResolve();await Promise.all([first,second]);
 assert.equal(calls.length,2);assert.equal(calls[0].data.responsible,'Ana');assert.equal(calls[1].data.responsible,'Bruno');
 await environment.window.Training.flush();assert.equal(calls.length,2);
 await environment.window.Training.flush(true);assert.equal(calls.length,3);
 assert.notEqual(calls[1].data.record_id,calls[2].data.record_id);
 currentName='Carla';let finishPending;
 environment.api=async(url,data)=>{calls.push({url,data});await new Promise(resolve=>finishPending=resolve);return {updated_at:'2026-10-15T12:00:00Z'};};
 const saving=environment.window.Training.flush(),pausing=environment.window.Training.pause();
 const count=calls.length;await environment.window.Training.flush(true);assert.equal(calls.length,count);
 finishPending();await Promise.all([saving,pausing]);await environment.window.Training.flush(true);assert.equal(calls.length,count);

 const cache=new Map(),uiEvents=[],ui={window:{addEventListener(){},Book:{value:()=>({points:[]}),load:value=>uiEvents.push(['load',value]),invalidateForms(){},autosave(){}},Drawing:{flush:async()=>uiEvents.push(['drawing-flush'])},Training:{pause:async()=>uiEvents.push(['pause']),resume:()=>uiEvents.push(['resume'])}},
 document:{getElementById:element},crypto:require('node:crypto').webcrypto,setTimeout:()=>1,clearTimeout(){},confirm:()=>true,localStorage:{getItem:key=>cache.get(key),setItem:(key,value)=>cache.set(key,value)},console};
 vm.createContext(ui);vm.runInContext(fs.readFileSync(path.join(web,'app.js'),'utf8'),ui);
 let snapshots=0,scheduledId=0;const scheduled=new Map();
 ui.window.Book.value=()=>{snapshots++;return {points:[]};};ui.setTimeout=(fn,delay)=>{const id=++scheduledId;scheduled.set(id,{fn,delay});return id;};ui.clearTimeout=id=>scheduled.delete(id);
 for(let i=0;i<100;i++)vm.runInContext('persist(true)',ui);
 assert.equal(snapshots,0,'Typing does not serialize every page at each keystroke');assert.equal(scheduled.size,1);
 const localSave=[...scheduled.values()][0];localSave.fn();assert.equal(snapshots,1);assert.equal(scheduled.size,0);
 vm.runInContext('persist(true);persist()',ui);assert.equal(snapshots,2);assert.equal(scheduled.size,0,'Explicit save cancels the pending copy');
 const cleared={draft_id:'new-id',services:[],editor:null,book:null,work_order:'',date:'2026-10-15',updated_at:'2026-10-15T12:00:00Z'};
 ui.response={draft:cleared};ui.events=uiEvents;
 vm.runInContext(`api=async(path,data)=>{events.push([path,data]);return response;};renderLabor=renderServices=showTab=()=>{};recalculate=async()=>{};S.draftId='old-id';S.services=[{labor_id:'test'}];S.editor={test:true};S.selected='test';S.editorTouched=true;`,ui);
 element('workOrder').value='Old job';element('responsible').value='Ana';
 await vm.runInContext('clearCurrentDraft()',ui);
 assert.equal(uiEvents[0][0],'pause');assert.equal(uiEvents.find(e=>e[0]==='/api/draft-clear')[1].draft_id,'old-id');
 assert.equal(uiEvents.at(-1)[0],'resume');assert.equal(element('workOrder').value,'');assert.equal(element('responsible').value,'');assert.equal(element('clearDraft').disabled,false);
 const saved=JSON.parse([...cache.values()][0]);assert.equal(saved.draft_id,'new-id');assert.deepEqual(saved.services,[]);assert.equal(saved.editor,null);
 ui.boot={draft:cleared,cleared_draft_ids:['old-id']};ui.stale={draft_id:'old-id',work_order:'Old job',updated_at:'2099-01-01T00:00:00Z'};
 assert.equal(vm.runInContext('chooseDraft(boot,stale).draft_id',ui),'new-id','A newer stale browser copy must not resurrect a cleared draft');
 ui.stale.draft_id='other-id';assert.equal(vm.runInContext('chooseDraft(boot,stale).draft_id',ui),'other-id','Unrelated drafts remain recoverable');
 vm.runInContext(`api=async()=>{throw Error('Offline');};S.draftId='unchanged';S.services=[{labor_id:'keep'}];`,ui);
 await assert.rejects(()=>vm.runInContext('clearCurrentDraft()',ui),/Offline/);
 assert.equal(vm.runInContext('S.draftId',ui),'unchanged');assert.equal(vm.runInContext('S.services.length',ui),1);assert.equal(element('clearDraft').disabled,false);assert.equal(uiEvents.at(-1)[0],'resume');
 console.log('OK: undo/redo, fila de autosalvamento, pausa, limpeza persistente, rejeição de cópia antiga e preservação em falha.');
})().catch(error=>{console.error(error);process.exitCode=1;});
