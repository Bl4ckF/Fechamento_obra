// Exercita a fila real; apenas PDF.js, canvas e o worker são substituídos.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const web=path.join(__dirname,'../web'),settle=()=>new Promise(setImmediate);
let renders=[],cancelled=0;
const page={rotate:0,getViewport:({scale})=>({width:1200*scale,height:800*scale}),render(options){let finish,fail;const promise=new Promise((resolve,reject)=>{finish=resolve;fail=reject;});const task={promise,cancel(){cancelled++;fail(Error('cancelled'));},finish,options};renders.push(task);return task;}};
const library={GlobalWorkerOptions:{},getDocument:()=>({promise:Promise.resolve({getPage:async()=>page}),destroy:async()=>{}})};
const env={window:{PDFText:{textFilter:()=>()=>true}},loadPDFLibrary:async()=>library,document:{createElement:()=>({width:0,height:0,getContext:()=>({})})}};
vm.createContext(env);vm.runInContext(fs.readFileSync(path.join(web,'croqui-quality.js'),'utf8'),env);
vm.runInContext(fs.readFileSync(path.join(web,'pdf-source.js'),'utf8').replace("await import('/vendor/pdfjs/pdf.min.mjs')",'await loadPDFLibrary()'),env);
const source={kind:'pdf',page:1},renderer=env.window.PDFSource;
(async()=>{
 const old=renderer.render('a.pdf',source,[1],false,true).catch(error=>error);await settle();assert.equal(renders.length,1);
 const requests=[];for(let i=2;i<=21;i++)requests.push(renderer.render('a.pdf',source,[i],false,true).catch(error=>error));
 await settle();assert.equal(renders.length,2,'Only the newest preview starts; intermediate requests never draw');assert.ok(cancelled>=1);
 const latest=renders.at(-1);assert.equal(latest.options.operationsFilter(21),false);assert.equal(latest.options.operationsFilter(1),true);latest.finish();
 const results=await Promise.all([old,...requests]);assert.equal(results.at(-1).original.width,1800);assert.equal(results.at(-1).original.height,1200);
 assert.ok(results.slice(1,-1).every(r=>r.name==='RenderingCancelledException'));
 assert.equal(await renderer.render('a.pdf',source,[21],false,true),results.at(-1),'Repeated previews share the completed image');
 const full=renderer.render('a.pdf',source,[21],true);await settle();const before=cancelled;
 const fresh=renderer.render('a.pdf',source,[22],false,true);await settle();assert.equal(cancelled,before,'New previews never cancel an explicit full export');
 renders.at(-1).finish();await settle();renders.at(-1).finish();const exported=await full;assert.equal(exported.original.width,6000);assert.equal(exported.original.height,4000);assert.equal(exported.clean.width,6000);
 await settle();renders.at(-1).finish();const freshPreview=await fresh;
 // Successive full exports release their pixels and never reuse a consumed canvas.
 for(let cycle=0;cycle<4;cycle++){
  const pending=renderer.forExport('a.pdf',source,[22],false);await settle();renders.at(-1).finish();const pictures=await pending;
  assert.equal(pictures.original.width,6000);renderer.release(pictures);assert.equal(pictures.original.width,1);
  assert.equal(freshPreview.original.width,1800,'Releasing a full export leaves the active preview intact');
 }
 // O worker recebe somente as fontes usadas para apagar textos editados.
 let message,transfer;class Worker{postMessage(data,items){message=data;transfer=items;queueMicrotask(()=>this.onmessage({data:{id:data.id,blob:{size:10}}}));}}
 class FileReader{readAsDataURL(){this.result='data:image/png;base64,OK';this.onload();}}
 const compact={window:{CroquiQuality:env.window.CroquiQuality,NetworkSymbols:{all:()=>[]}},Worker,OffscreenCanvas:class{},createImageBitmap:async image=>({...image,close(){}}),FileReader};vm.createContext(compact);
 vm.runInContext(fs.readFileSync(path.join(web,'croqui-render.js'),'utf8'),compact);
 const doc={objects:[{id:'edit',pdf_text_id:'text_1',type:'text',text:'Novo'}],pdf_texts:[{id:'text_1',box:{x:10}},{id:'text_2',box:{x:20}}],pdf_lines:[{id:'line_1'}],background_ref:'a.png'};
 await compact.window.CroquiRender.png(doc,{original:{width:6000,height:4000},clean:{width:6000,height:4000}});
 assert.equal(message.doc.pdf_lines,undefined);assert.equal(message.doc.pdf_texts.length,1);assert.equal(message.doc.pdf_texts[0].id,'text_1');assert.equal(message.doc.objects[0].text,'Novo');assert.equal(message.size.width,6000);assert.equal(transfer.length,2);
 assert.equal(doc.pdf_texts.length,2);assert.equal(doc.pdf_lines.length,1,'Export leaves the editable sources intact');
 let transfers=0;const movable=()=>({width:6000,height:4000,transferToImageBitmap(){transfers++;return {width:6000,height:4000,close(){}};}});
 await compact.window.CroquiRender.png(doc,{original:movable(),clean:movable()});assert.equal(transfers,2,'Full-resolution pixels move to the worker without a second copy');assert.equal(message.size.width,6000);
 console.log('OK: fila descarta prévias antigas, protege exportação completa e transfere apenas as geometrias necessárias ao worker.');
})().catch(error=>{console.error(error);process.exitCode=1;});
