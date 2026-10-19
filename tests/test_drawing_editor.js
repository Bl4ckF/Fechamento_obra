/* Fluxos do editor sobreposto à página; não substitui a conferência visual no navegador. */
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const elements=new Map();let focused=null;
function context(){const data={texts:[],measurements:0,measureText(t){this.measurements++;return {width:String(t).length*10,fontBoundingBoxAscent:18,fontBoundingBoxDescent:4};},clearRect(){this.texts=[];this.paints=(this.paints||0)+1;},fillText(t){this.texts.push(t);}};return new Proxy(data,{get:(o,k)=>o[k]??(()=>{}),set:(o,k,v)=>(o[k]=v,true)});}
class Element{
 constructor(tag='div'){this.tag=tag;this.dataset={};this.style={};this.children=[];this.value='';this.checked=false;this.disabled=false;this.width=1200;this.height=800;this.clientWidth=1202;this.clientHeight=700;this.scrollLeft=0;this.scrollTop=0;this.textContent='';this.context=context();this.classes=new Set();this.classList={toggle:(name,on)=>on?this.classes.add(name):this.classes.delete(name)};}
 set innerHTML(html){this.html=html;for(const match of html.matchAll(/<(\w+)\b[^>]*\bid="([^"]+)"[^>]*>/g)){const el=new Element(match[1]);el.id=match[2];el.value=match[0].match(/\bvalue="([^"]*)"/)?.[1]||'';elements.set(el.id,el);}}
 get innerHTML(){return this.html;}
 get innerText(){return this.textContent;}
 appendChild(child){this.children.push(child);child.parent=this;}
 replaceChildren(...children){this.children=[];children.forEach(c=>this.appendChild(c));}
 getBoundingClientRect(){const view=elements.get('pdfEditorViewport');if(this.id==='pdfEditorStage'){const scale=Number(this.style.transform?.match(/scale\(([^)]+)\)/)?.[1])||1;return {left:-view.scrollLeft,top:-view.scrollTop,width:1200*scale,height:800*scale};}return {left:0,top:0,width:this.clientWidth,height:this.clientHeight};}
 setPointerCapture(id){this.captured=id;}hasPointerCapture(id){return this.captured===id;}releasePointerCapture(){this.captured=null;}
 remove(){if(this.parent)this.parent.children=this.parent.children.filter(x=>x!==this);}
 setAttribute(name,value){this[name]=value;}
 focus(){if(focused===this)return;focused?.blur();focused=this;this.onfocus?.();}
 blur(){if(focused!==this)return;focused=null;this.onblur?.();}
 showModal(){this.open=true;}close(){this.open=false;}
 scrollIntoView(){} addEventListener(name,fn){(this.events??={})[name]=fn;}
 getContext(){return this.context;}
 toDataURL(){return 'data:image/png;base64,'+Buffer.from(JSON.stringify({texts:this.context.texts,width:this.width,height:this.height})).toString('base64');}
}
const panel=new Element(),document={getElementById:id=>elements.get(id),querySelector:selector=>selector==='dialog[open]'?(elements.get('symbolEditorDialog')?.open?elements.get('symbolEditorDialog'):null):panel,body:new Element(),addEventListener(name,fn){(this.events??={})[name]=fn;},get activeElement(){return focused;},createElement:tag=>new Element(tag),createElementNS:(ns,tag)=>new Element(tag)};
let missingImage=false;
class Image{constructor(){this.width=6000;this.height=4000;}set src(value){Promise.resolve().then(()=>missingImage?this.onerror():this.onload());}}
const env={window:{},document,Image,crypto:require('node:crypto').webcrypto,setTimeout:()=>1,clearTimeout(){},console};vm.createContext(env);
const personal=new Map();let failSymbols=false;env.api=async(path,payload)=>{if(path!=='/api/custom-symbols')throw Error(path);if(failSymbols)throw Error('Falha simulada ao gravar');if(!payload)return [...personal.values()];const old=personal.get(payload.symbol.id);assert.equal(payload.expected_revision,old?.revision||0);const saved={...JSON.parse(JSON.stringify(payload.symbol)),revision:(old?.revision||0)+1};personal.set(saved.id,saved);return saved;};
for(const f of ['croqui-quality.js','pdf-text.js','pdf-lines.js','network-symbols.js','drawing-ui.js','symbol-editor.js','pdf-search.js','drawing-transform.js','croqui-render.js','drawing.js'])vm.runInContext(fs.readFileSync(path.join(__dirname,'../web',f),'utf8'),env);
env.window.NetworkSymbols.setCatalog(JSON.parse(fs.readFileSync(path.join(__dirname,'../data/simbolos_rede.json'),'utf8')));
let recoveredAssets=0;
let changed,images=[],searchDocuments=null,searchPageIndex=0,failNavigation=false;
const drawing=env.window.Drawing;
drawing.init({onRecover:async()=>{recoveredAssets++;missingImage=false;return {original:'d'.repeat(64)+'.png',clean:'b'.repeat(64)+'.png'};},getPages:()=>searchDocuments,getPageId:()=>searchDocuments?.[searchPageIndex]?.id,onSearchPage:async id=>{if(failNavigation)throw Error('Falha ao salvar página');await drawing.flush();searchPageIndex=searchDocuments.findIndex(p=>p.id===id);drawing.load(searchDocuments[searchPageIndex].drawing);},onChange:doc=>{changed=doc;if(searchDocuments)searchDocuments[searchPageIndex].drawing=doc;},onImage:async(data,signature)=>{images.push({...JSON.parse(Buffer.from(data.split(',')[1],'base64')),doc:JSON.parse(signature)});}});
const source={id:'pdf_0',text:'PONTO ANTIGO',x1:40,y1:70,size:20,rotation:0,font:'Arial',color:'#111111',box:{x:38,y:48,w:180,h:26},text_width:175};
const node=()=>elements.get('pdfTextLayer').children[0];
const type=text=>{node().focus();node().textContent=text;node().oninput();};
(async()=>{
 await drawing.setBackground('a'.repeat(64)+'.png',{kind:'pdf',name:'Planta.pdf',page:1},{cleanRef:'b'.repeat(64)+'.png',texts:[source]});
 assert.equal(changed.pdf_texts.length,1);assert.equal(node().contentEditable,'plaintext-only');assert.equal(node().textContent,'PONTO ANTIGO');
 assert.ok(!elements.has('dTool'));assert.ok(!elements.has('dPdfList'));assert.ok(!panel.innerHTML.includes('Desenhar'));
 node().focus();assert.equal(elements.get('dFont').disabled,false);assert.equal(node().style.color,'#111111');
 type('PONTO CORRIGIDO');await drawing.flush();
 assert.equal(changed.objects[0].text,'PONTO CORRIGIDO');assert.equal(changed.objects[0].pdf_text_id,'pdf_0');
 assert.equal(node().textContent,'PONTO CORRIGIDO','Autosave must not replace active text / native selection');
 assert.ok(images.at(-1).texts.includes('PONTO CORRIGIDO'),'Export retains text while inline editor has focus');
 const stored=JSON.parse(JSON.stringify(changed));drawing.load(null);drawing.load(stored);
 assert.equal(node().textContent,'PONTO CORRIGIDO');node().focus();
 elements.get('dDelete').onclick();await drawing.flush();assert.equal(changed.objects[0].text,'');
 elements.get('dUndo').onclick();assert.equal(changed.objects[0].text,'PONTO CORRIGIDO');
 node().focus();elements.get('dRestoreText').onclick();await drawing.flush();
 assert.equal(changed.objects.length,0);assert.equal(node().textContent,'PONTO ANTIGO');
 type('OUTRO TEXTO');elements.get('dRotation').value='90';elements.get('dRotation').onchange();assert.equal(changed.objects[0].rotation,90);assert.equal(node().style.transform,'rotate(90deg)');
 elements.get('dClear').onclick();await drawing.flush();assert.equal(changed.objects.length,0);assert.equal(changed.background_ref,'a'.repeat(64)+'.png');assert.equal(node().textContent,'PONTO ANTIGO');
 elements.get('dUndo').onclick();await drawing.flush();assert.equal(changed.objects[0].text,'OUTRO TEXTO');
 elements.get('dPdfSearch').value='outro';await elements.get('dFind').onclick();assert.equal(node().style.color,'#111111');
 // Colocar, mover, editar, duplicar, reabrir e excluir um símbolo sobre o PDF.
 const palette=elements.get('symbolPalette');assert.ok(palette.children.length>100);
 palette.children[0].onclick();const stage=elements.get('pdfEditorStage');
 stage.events.pointerdown({button:0,clientX:220,clientY:310,preventDefault(){},stopPropagation(){}});
 let symbol=changed.objects.find(o=>o.type==='symbol');assert.ok(symbol);assert.equal(symbol.x1,220);assert.equal(symbol.y1,310);
 let hit=elements.get('symbolLayer').children[0];
 hit.onpointerdown({button:0,clientX:220,clientY:310,pointerId:1,preventDefault(){},stopPropagation(){}});
 hit.onpointermove({clientX:260,clientY:350});hit.onpointerup({pointerId:1});
 symbol=changed.objects.find(o=>o.type==='symbol');assert.equal(symbol.x1,260);assert.equal(symbol.y1,350);
 elements.get('dUndo').onclick();assert.equal(changed.objects.find(o=>o.type==='symbol').x1,220);
 hit=elements.get('symbolLayer').children[0];hit.focus();
 elements.get('sScale').value='150';elements.get('sRotation').value='90';elements.get('sStatus').value='retirar';elements.get('sOpaque').checked=true;elements.get('sLabel').value='P3';elements.get('sLabel').oninput();await drawing.flush();
 symbol=changed.objects.find(o=>o.type==='symbol');assert.equal(symbol.rotation,90);assert.equal(symbol.status,'retirar');assert.equal(symbol.opaque,true);assert.equal(symbol.label,'P3');assert.equal(symbol.size,105);
 elements.get('sDuplicate').onclick();assert.equal(changed.objects.filter(o=>o.type==='symbol').length,2);
 const withSymbols=JSON.parse(JSON.stringify(changed));drawing.load(null);drawing.load(withSymbols);assert.equal(elements.get('symbolLayer').children.length,2);
 assert.ok(!elements.has('dSymbolMode'));assert.ok(!elements.has('dTextMode'));hit=elements.get('symbolLayer').children[0];hit.focus();elements.get('sDelete').onclick();assert.equal(changed.objects.filter(o=>o.type==='symbol').length,1);
 elements.get('dUndo').onclick();assert.equal(changed.objects.filter(o=>o.type==='symbol').length,2);
 elements.get('dClear').onclick();assert.equal(changed.objects.length,0);elements.get('dUndo').onclick();assert.equal(changed.objects.filter(o=>o.type==='symbol').length,2);
 await drawing.flush();assert.ok(images.at(-1).doc.objects.some(o=>o.type==='symbol'));
 assert.equal(images.at(-1).width,6000);assert.equal(images.at(-1).height,4000,'Export preserves source detail instead of using the old 2400 x 1600 bitmap');
 // Mover texto pela alça mantém o conteúdo e o histórico; as letras seguem editáveis.
 node().focus();const handle=elements.get('textMoveHandle');assert.equal(handle.hidden,false);
 const beforeMove=JSON.parse(JSON.stringify(changed.objects.find(o=>o.pdf_text_id==='pdf_0')));
 handle.onpointerdown({button:0,pointerId:41,clientX:40,clientY:40,preventDefault(){},stopPropagation(){}});
 handle.onpointermove({pointerId:41,clientX:120,clientY:90,preventDefault(){}});handle.onpointerup({pointerId:41});
 assert.equal(changed.objects.find(o=>o.pdf_text_id==='pdf_0').x1,beforeMove.x1+80);assert.equal(changed.objects.find(o=>o.pdf_text_id==='pdf_0').y1,beforeMove.y1+50);
 await drawing.flush();const moved=JSON.parse(JSON.stringify(changed));drawing.load(null);drawing.load(moved);assert.equal(node().style.left,(beforeMove.x1+80)+'px');
 node().focus();type('TEXTO MOVIDO');assert.equal(changed.objects.find(o=>o.pdf_text_id==='pdf_0').text,'TEXTO MOVIDO');await drawing.flush();
 // Nova linha: duas pontas, movimento e edição do comprimento, no mesmo editor.
 elements.get('dNewLine').onclick();const lineEvent=(x,y)=>({button:0,pointerId:51,clientX:x,clientY:y,preventDefault(){},stopPropagation(){}});
 stage.events.pointerdown(lineEvent(100,200));stage.events.pointerup(lineEvent(100,200));stage.events.pointerdown(lineEvent(300,230));
 let line=changed.objects.find(o=>o.type==='line');assert.equal(line.x1,100);assert.equal(line.x2,300);
 let lineHit=elements.get('lineLayer').children[0];lineHit.onpointerdown(lineEvent(150,200));lineHit.onpointermove(lineEvent(200,260));lineHit.onpointerup(lineEvent(200,260));
 line=changed.objects.find(o=>o.type==='line');assert.equal(line.x1,150);assert.equal(line.y1,260);
 const end=elements.get('lHandleEnd');end.onpointerdown(lineEvent(350,290));end.onpointermove(lineEvent(420,320));end.onpointerup(lineEvent(420,320));assert.equal(changed.objects.find(o=>o.type==='line').x2,420);
 elements.get('lColor').value='#cc6600';elements.get('lWidth').value='4';elements.get('lDash').value='dashed';elements.get('lArrow').value='both';elements.get('lColor').onchange();await drawing.flush();
 line=changed.objects.find(o=>o.type==='line');assert.equal(line.width,4);assert.equal(line.color,'#cc6600');assert.equal(line.arrow,'both');
 elements.get('lDuplicate').onclick();assert.equal(changed.objects.filter(o=>o.type==='line').length,2);elements.get('lDelete').onclick();assert.equal(changed.objects.filter(o=>o.type==='line').length,1);
 node().focus();assert.equal(elements.get('textControls').hidden,false);assert.equal(elements.get('lineControls').hidden,true);await drawing.flush();
 // A navegação não altera os objetos nem entra no histórico de edição.
 const view=elements.get('pdfEditorViewport'),zoom=elements.get('dZoom'),snapshot=JSON.stringify(changed),savedCount=images.length;
 const event=extra=>({preventDefault(){this.prevented=true;},stopPropagation(){this.stopped=true;},...extra});
 zoom.value='2';zoom.onchange();view.scrollLeft=200;view.scrollTop=100;
 const before=stage.getBoundingClientRect(),anchor={clientX:300,clientY:200},world={x:(anchor.clientX-before.left)*1200/before.width,y:(anchor.clientY-before.top)*800/before.height};
 const wheel=event({...anchor,deltaY:-100,deltaMode:0});view.events.wheel(wheel);assert.equal(wheel.prevented,true);assert.ok(Number(zoom.value)>2);
 const after=stage.getBoundingClientRect();assert.ok(Math.abs((anchor.clientX-after.left)*1200/after.width-world.x)<.00001);assert.ok(Math.abs((anchor.clientY-after.top)*800/after.height-world.y)<.00001);
 assert.ok(elements.get('drawingCanvas').width>1200,'Screen backing pixels grow with zoom');
 const start={left:view.scrollLeft,top:view.scrollTop};view.events.pointerdown(event({button:1,pointerId:7,clientX:500,clientY:300}));assert.equal(view.captured,7);assert.equal(view.classes.has('panning'),true);
 view.events.pointermove(event({pointerId:8,clientX:490,clientY:290}));assert.equal(view.scrollLeft,start.left,'An unrelated pointer does not pan');
 view.events.pointermove(event({pointerId:7,clientX:460,clientY:275}));assert.equal(view.scrollLeft,start.left+40);assert.equal(view.scrollTop,start.top+25);
 view.events.pointerup(event({pointerId:7}));assert.equal(view.classes.has('panning'),false);assert.equal(view.captured,null);
 view.events.pointerdown(event({button:1,pointerId:9,clientX:500,clientY:300}));view.events.pointercancel();assert.equal(view.classes.has('panning'),false);
 for(let i=0;i<20;i++)view.events.wheel(event({...anchor,deltaY:-120,deltaMode:1}));assert.equal(Number(zoom.value),8);assert.ok(elements.get('drawingCanvas').width*elements.get('drawingCanvas').height<=24000000);
 for(let i=0;i<30;i++)view.events.wheel(event({...anchor,deltaY:1,deltaMode:2}));assert.equal(Number(zoom.value),.25);
 await drawing.flush();assert.equal(JSON.stringify(changed),snapshot);assert.equal(images.length,savedCount,'Zoom and pan do not autosave unchanged content');
 palette.children[0].onclick();stage.events.pointerdown(event({button:1,clientX:220,clientY:310}));assert.equal(JSON.stringify(changed),snapshot,'Middle click never inserts an armed symbol');
 // Após ampliar e deslocar, inserir continua usando as coordenadas do projeto.
 zoom.value='3';zoom.onchange();view.scrollLeft=300;view.scrollTop=180;
 stage.events.pointerdown(event({button:0,clientX:300,clientY:120}));symbol=changed.objects.at(-1);assert.equal(symbol.x1,200);assert.equal(symbol.y1,100);
 await drawing.setBackground('c'.repeat(64)+'.png',{kind:'image',name:'Outro.png'});
 assert.equal(changed.pdf_texts.length,0);assert.equal(changed.objects.length,0);assert.equal(elements.get('symbolLayer').children.length,0);assert.equal(elements.get('pdfTextLayer').children.length,0);assert.equal(elements.get('pdfNoText').hidden,false);
 // Linha original: a geometria editada omite somente o operador correspondente.
 let exclusions=[];env.window.PDFSource={render:async(ref,source,hidden)=>{exclusions.push({ref,source,hidden});return {original:new Image(),clean:new Image()};}};
 const native={id:'pdfline_12',operator_index:12,type:'line',x1:100,y1:300,x2:800,y2:300,width:2,color:'#000000',dash:'solid',arrow:'none',label:''};
 await drawing.setBackground('a'.repeat(64)+'.png',{kind:'pdf',name:'Rede.pdf',page:2},{cleanRef:'b'.repeat(64)+'.png',texts:[source],pdfRef:'f'.repeat(64)+'.pdf',lines:[native]});
 assert.equal(exclusions.length,0);lineHit=elements.get('lineLayer').children[0];lineHit.focus();elements.get('lColor').value='#ff0000';elements.get('lColor').onchange();await drawing.flush();
 assert.equal(changed.objects[0].pdf_line_id,'pdfline_12');assert.deepEqual(Array.from(exclusions.at(-1).hidden),[12]);
 elements.get('lRestore').onclick();await drawing.flush();assert.equal(changed.objects.length,0);elements.get('lDelete').onclick();await drawing.flush();assert.equal(changed.objects[0].deleted,true);assert.equal(elements.get('lineLayer').children.length,0);
 elements.get('dUndo').onclick();await drawing.flush();assert.equal(elements.get('lineLayer').children.length,1);assert.equal(changed.objects.length,0);
 // As prévias de arraste são agrupadas por quadro e usam menos pixels, sem alterar a origem.
 const stressLine={id:'line_stress',type:'line',x1:200,y1:200,x2:500,y2:250,color:'#112233',width:2};
 drawing.load({version:1,background_ref:'a'.repeat(64)+'.png',objects:[stressLine]});await Promise.resolve();await Promise.resolve();
 zoom.value='8';zoom.onchange();view.scrollLeft=view.scrollTop=0;
 const stressHit=elements.get('lineLayer').children[0],stressEvent=(x,y)=>({button:0,pointerId:99,clientX:x*8,clientY:y*8,preventDefault(){},stopPropagation(){}}),frames=[];
 env.window.requestAnimationFrame=fn=>{frames.push(fn);return frames.length;};stressHit.onpointerdown(stressEvent(250,220));const paints=elements.get('drawingCanvas').context.paints;
 for(let i=1;i<=100;i++)stressHit.onpointermove(stressEvent(250+i,220+i/2));
 assert.equal(frames.length,1);assert.equal(elements.get('drawingCanvas').context.paints,paints);frames.shift()();assert.equal(elements.get('drawingCanvas').width,1800);
 stressHit.onpointerup(stressEvent(350,270));assert.equal(changed.objects[0].x1,300);assert.equal(elements.get('drawingCanvas').width,6000);assert.equal(stressLine.x1,200);
 delete env.window.requestAnimationFrame;
 // v10: transformar diretamente na página, cancelar seleção e preservar histórico.
 const raw={version:1,width:1200,height:800,background_ref:'a'.repeat(64)+'.png',background_source:{kind:'pdf',name:'Teste',page:1},pdf_text_background_ref:'b'.repeat(64)+'.png',pdf_texts:[source],objects:[]};
 drawing.load(raw);await Promise.resolve();await Promise.resolve();
 node().focus();assert.equal(elements.get('tRotate').hidden,false);
 const tRotate=elements.get('tRotate'),transformEvent=(x,y,id=70)=>({button:0,pointerId:id,clientX:x,clientY:y,preventDefault(){},stopPropagation(){}});
 tRotate.onpointerdown(transformEvent(140,70));tRotate.onpointermove({...transformEvent(40,170),shiftKey:true});tRotate.onpointerup(transformEvent(40,170));
 assert.equal(changed.objects[0].rotation,90);assert.equal(changed.objects[0].text,source.text);assert.equal(changed.objects[0].pdf_text_id,source.id);
 const tScale=elements.get('tScaleSE');tScale.onpointerdown(transformEvent(140,70,71));tScale.onpointermove(transformEvent(240,70,71));tScale.onpointerup(transformEvent(240,70,71));
 assert.equal(changed.objects[0].size,40);assert.equal(changed.objects[0].text_width,350);
 const previous=JSON.stringify(changed);document.events.keydown({key:'Escape',preventDefault(){}});
 assert.equal(elements.get('textControls').hidden,true);assert.equal(tRotate.hidden,true);assert.equal(JSON.stringify(changed),previous);
 elements.get('dUndo').onclick();assert.equal(changed.objects[0].size,20,'Deselect does not consume undo history');
 node().focus();stage.events.pointerdown({...transformEvent(600,600),target:elements.get('drawingCanvas')});assert.equal(elements.get('textControls').hidden,true);
 node().focus();tScale.onpointerdown(transformEvent(140,70,72));tScale.onpointermove(transformEvent(340,70,72));stage.events.keydown({key:'Escape',preventDefault(){},stopPropagation(){}});assert.equal(changed.objects[0].size,20,'Escape cancels an uncommitted resize');assert.equal(tScale.captured,null);
 type('REDE INSTALAÇÃO P17');elements.get('dPdfSearch').value='instalacao p17';elements.get('dPdfSearch').oninput();assert.equal(elements.get('pdfSearchResults').children.length,1);assert.equal(node().classes.has('search-match'),true);
 elements.get('dPdfSearch').value='PONTO ANTIGO';elements.get('dPdfSearch').oninput();assert.equal(elements.get('pdfSearchResults').children.length,0,'Old text must not match after editing');
 drawing.resetSearch();assert.equal(elements.get('pdfSearchPanel').hidden,true);
 // Criação, salvamento com falha, inserção, edição e reabertura de simbologia pessoal.
 await elements.get('dSymbolEditor').onclick();assert.equal(elements.get('seName').value,'Nova simbologia');
 const seCanvas=elements.get('seCanvas');seCanvas.clientWidth=seCanvas.clientHeight=480;
 elements.get('seName').value='Minha chave';elements.get('seName').oninput();elements.get('seTag').value='CH-P17';elements.get('seTag').oninput();elements.get('seTool').value='line';elements.get('seTool').onchange();
 seCanvas.onpointerdown(transformEvent(160,240,80));seCanvas.onpointermove(transformEvent(320,240,80));seCanvas.onpointerup(transformEvent(320,240,80));
 failSymbols=true;await assert.rejects(env.window.SymbolEditor.flush(),/Falha simulada/);assert.equal(personal.size,0);failSymbols=false;await env.window.SymbolEditor.flush();
 const custom=[...personal.values()][0];assert.equal(custom.name,'Minha chave');assert.deepEqual(custom.ops,[['line',-40,0,40,0]]);assert.equal(env.window.NetworkSymbols.all().length,120);
 await elements.get('seUse').onclick();stage.events.pointerdown(transformEvent(500,400,81));
 let customPlaced=changed.objects.find(o=>o.symbol_id===custom.id);assert.ok(customPlaced.symbol_definition);const customId=customPlaced.id;
 await elements.get('sEditDrawing').onclick();elements.get('seElements').value='0';elements.get('seElements').onchange();
 const properties=elements.get('seProperties').children;properties[2].children[0].value='60';properties[2].children[0].oninput();await env.window.SymbolEditor.flush();
 customPlaced=changed.objects.find(o=>o.id===customId);assert.equal(customPlaced.symbol_definition.ops[0][3],60);await elements.get('seClose').onclick();
 // Uma revisão alterada em outra aba pode ser preservada como cópia, sem perder o rascunho.
 await elements.get('sEditDrawing').onclick();const originalCustom=personal.get(custom.id);personal.set(custom.id,{...originalCustom,revision:originalCustom.revision+1});elements.get('seName').value='Minha revisão local';elements.get('seName').oninput();await assert.rejects(env.window.SymbolEditor.flush());await elements.get('seCopy').onclick();assert.equal(personal.size,2);assert.ok([...personal.values()].some(s=>s.id!==custom.id&&s.name.includes('Minha revisão local')));await elements.get('seClose').onclick();
 const withCustom=JSON.parse(JSON.stringify(changed));env.window.NetworkSymbols.setCustom([]);drawing.load(null);drawing.load(withCustom);await Promise.resolve();await drawing.flush();
 assert.equal(elements.get('symbolLayer').children.length,1,'Placed symbols are self-contained after reopening without the library');
 // Cria uma nova inserção a partir da definição embutida preservada no registro.
 assert.ok(env.window.NetworkSymbols.bounds(customPlaced).w>0);
 // Busca navega entre páginas sem perder os textos alterados nem a consulta.
 searchDocuments=[{id:'page_first',drawing:{...JSON.parse(JSON.stringify(raw)),pdf_texts:[{...source,text:'CIRCUITO REDE P1'}]}},{id:'page_second',drawing:{...JSON.parse(JSON.stringify(raw)),background_source:{kind:'pdf',name:'Teste.pdf',page:7},pdf_texts:[{...source,text:'CIRCUITO REDE P7'}]}}];
 searchPageIndex=0;drawing.load(searchDocuments[0].drawing);await Promise.resolve();await Promise.resolve();
 elements.get('dPdfSearch').value='circuito rede';elements.get('dPdfSearch').oninput();assert.equal(elements.get('pdfSearchResults').children.length,2);
 await elements.get('dFind').onclick();assert.equal(searchPageIndex,0);await elements.get('dFind').onclick();assert.equal(searchPageIndex,1);assert.equal(node().textContent,'CIRCUITO REDE P7');assert.equal(elements.get('dPdfSearch').value,'circuito rede');
 type('CIRCUITO CORRIGIDO P7');await elements.get('dFind').onclick();assert.equal(searchPageIndex,0);assert.equal(searchDocuments[1].drawing.objects[0].text,'CIRCUITO CORRIGIDO P7');
 elements.get('dPdfSearch').value='circuito';elements.get('dPdfSearch').oninput();failNavigation=true;await elements.get('pdfSearchResults').children[1].onclick();assert.equal(searchPageIndex,0);assert.match(elements.get('drawingStatus').textContent,/Falha ao salvar/);failNavigation=false;
 elements.get('dSearchScope').value='current';elements.get('dSearchScope').onchange();assert.equal(elements.get('pdfSearchResults').children.length,1);drawing.resetSearch();
 const quality=env.window.CroquiQuality;
 for(const [w,h] of [[600,400],[12000,4000],[4000,12000],[9000,9000]]){const size=quality.sourceSize(w,h);assert.ok(size.width<=6000&&size.height<=6000&&size.width*size.height<=24000000);assert.ok(size.width<=w&&size.height<=h);assert.ok(Math.abs(size.width/size.height-w/h)<.001);}
 assert.equal(quality.sourceSize(600,400,true).width,6000);
 assert.throws(()=>quality.pngData({toDataURL:()=> 'data:,'}),/preparar/);
 assert.throws(()=>quality.pngData({toDataURL:()=> 'data:image/png;base64,'+'A'.repeat(42666668)}),/32 MB/);
 // Página densa: seleção e zoom não devem reprocessar os 3.000 textos / 5.000 caminhos.
 searchDocuments=null;let paths=0;const pathData=env.window.PDFLines.pathData;env.window.PDFLines.pathData=o=>{paths++;return pathData(o);};
 const denseTexts=Array.from({length:3000},(_,i)=>({...source,id:'pdf_'+i,text:'TEXTO '+i,text_width:undefined}));
 const denseLines=Array.from({length:5000},(_,i)=>({...native,id:'pdfline_'+i,operator_index:i,type:'path',commands:[['M',i%1000,50],...Array.from({length:19},(_,j)=>['L',j*10,100+i%700])]}));
 drawing.load({...raw,pdf_source_ref:'f'.repeat(64)+'.pdf',pdf_texts:denseTexts,pdf_lines:denseLines});
 for(let i=0;i<8;i++)await Promise.resolve();
 const display=elements.get('drawingCanvas'),measureBefore=display.context.measurements,pathsBefore=paths;
 for(let i=0;i<10;i++){elements.get('lineLayer').children[i].focus();zoom.value=String(i%2?2:1);zoom.onchange();}
 assert.equal(display.context.measurements,measureBefore,'Selection/zoom reuses measured PDF text');assert.equal(paths,pathsBefore,'Selection/zoom reuses original path geometry');
 // A roda agrupa a renderização e recupera a nitidez após parar, sem gravar a vista.
 let now=10000,nextTimer=0;const timers=new Map(),zoomFrames=[];
 env.Date=class extends Date{static now(){return now;}};env.setTimeout=(fn,delay)=>{const id=++nextTimer;timers.set(id,{fn,delay});return id;};env.clearTimeout=id=>timers.delete(id);
 env.window.requestAnimationFrame=fn=>{zoomFrames.push(fn);return zoomFrames.length;};
 const initialImages=images.length,initialPaints=display.context.paints;
 for(let i=0;i<30;i++)view.events.wheel(event({deltaY:-40,clientX:300,clientY:200}));
 assert.equal(zoomFrames.length,1);assert.equal(display.context.paints,initialPaints);zoomFrames.shift()();assert.equal(display.width,1800);
 const nav=[...timers].find(([,v])=>v.delay===180);timers.delete(nav[0]);nav[1].fn();zoomFrames.shift()();assert.equal(display.width,6000);assert.equal(images.length,initialImages);
 delete env.window.requestAnimationFrame;
 // Digitação salva o documento imediatamente; PNG antigo não entra em um ciclo de exportações.
 type('EDIÇÃO A');const firstDoc=changed;assert.equal(firstDoc.objects[0].text,'EDIÇÃO A');assert.ok([...timers.values()].some(t=>t.delay===3000));
 await drawing.flush({automatic:true});assert.equal(images.length,initialImages,'No PNG while the user is typing');
 const png=env.window.CroquiRender.png;let releaseImage,pngCalls=0;
 env.window.CroquiRender.png=async(...args)=>{pngCalls++;if(pngCalls===1)await new Promise(resolve=>releaseImage=resolve);return png(...args);};
 now+=4000;const automatic=drawing.flush({automatic:true});for(let i=0;i<8;i++)await Promise.resolve();assert.equal(pngCalls,1);
 type('EDIÇÃO B');assert.equal(changed.pdf_texts,firstDoc.pdf_texts);assert.equal(changed.pdf_lines,firstDoc.pdf_lines,'Autosave snapshots share immutable source geometry');assert.equal(firstDoc.objects[0].text,'EDIÇÃO A');
 releaseImage();await automatic;assert.equal(pngCalls,1,'Automatic export waits for another idle period');assert.equal(images.length,initialImages,'An obsolete bitmap is not uploaded');
 await drawing.flush();assert.equal(images.at(-1).doc.objects[0].text,'EDIÇÃO B');assert.equal(images.at(-1).width,6000);assert.equal(images.at(-1).height,4000,'Explicit save always includes the latest full-quality edit');
 type('EDIÇÃO RECUPERADA');const recovered=JSON.parse(JSON.stringify(changed)),imagesBeforeRestore=images.length;
 drawing.load(null);drawing.load(recovered,recovered.background_ref,true);await drawing.flush();
 assert.equal(images.length,imagesBeforeRestore+1);assert.equal(images.at(-1).doc.objects[0].text,'EDIÇÃO RECUPERADA','An edit saved before PNG generation is rebuilt after reopening');
 // Recover missing preview assets from the saved original, without losing edits.
 missingImage=true;let recoveryCount=0;
 env.window.PDFSource={render:async()=>{recoveryCount++;return {original:new Image(),clean:new Image()};}};
 drawing.load({...recovered,pdf_source_ref:'e'.repeat(64)+'.pdf'},null,true);await drawing.flush();
 assert.equal(recoveryCount,1);assert.equal(recoveredAssets,1);assert.equal(images.at(-1).doc.background_ref,'d'.repeat(64)+'.png');assert.equal(images.at(-1).doc.objects[0].text,'EDIÇÃO RECUPERADA');
 // Failure can be retried on the same document after media is restored.
 missingImage=true;const absent={...recovered,pdf_source_ref:null,background_ref:'c'.repeat(64)+'.png'};
 drawing.load(absent,null,true);await assert.rejects(()=>drawing.flush(),/dados\/media/);
 missingImage=false;drawing.load(absent,null,true);await drawing.flush();
 assert.equal(images.at(-1).doc.objects[0].text,'EDIÇÃO RECUPERADA');
 console.log('OK: editor integrado; página de 3.000 textos e 5.000 traços; cache, zoom agrupado, autosave sem PNG obsoleto, exportação 6000 × 4000 e recursos anteriores.');
})().catch(error=>{console.error(error);process.exitCode=1;});
