'use strict';
(() => {
 const clone=x=>JSON.parse(JSON.stringify(x)),blank=()=>({version:1,width:1200,height:800,objects:[],background_ref:null});
 class DrawingModel{
  constructor(doc){this.doc=clone(doc||blank());this.undoStack=[];this.redoStack=[];}
  commit(next){const {pdf_texts,pdf_lines,objects=[],...rest}=next,copy=clone(rest),previous=new Set(this.doc.objects);copy.objects=objects.map(o=>previous.has(o)?o:clone(o));for(const [key,value] of [['pdf_texts',pdf_texts],['pdf_lines',pdf_lines]])if(value)copy[key]=value===this.doc[key]?value:clone(value);this.undoStack.push(this.doc);if(this.undoStack.length>60)this.undoStack.shift();this.redoStack=[];this.doc=copy;}
  undo(){if(!this.undoStack.length)return false;this.redoStack.push(this.doc);this.doc=this.undoStack.pop();return true;}
  redo(){if(!this.redoStack.length)return false;this.undoStack.push(this.doc);this.doc=this.redoStack.pop();return true;}
 }
 let model=new DrawingModel(),canvas,ctx,callbacks,selected='',active='',background=null,textBackground=null,backgroundRef=null,backgroundError=null,backgroundPromise=Promise.resolve(),timer,inFlight=null,lastRendered='',loadedKey='',dirty=false,zoom=1;
 const textNodes=new Map(),symbolNodes=new Map(),lineNodes=new Map();
 // As fontes do PDF e os documentos confirmados são imutáveis entre edições.
 const sourceTexts=new WeakMap(),textMetrics=new WeakMap(),fontBaselines=new Map(),linePaths=new WeakMap(),textMaps=new WeakMap();
 let revision=0,lastActivity=0,navigationTimer,navigating=false,loadedDoc=null;
 let assetKey='',assetPromise=null;
 const IMAGE_IDLE_MS=3000;
 function activity(){lastActivity=Date.now();}
 function editableText(source){if(!sourceTexts.has(source))sourceTexts.set(source,window.PDFText.editable(source));return sourceTexts.get(source);}
 function sourceMap(sources){if(!textMaps.has(sources))textMaps.set(sources,new Map(sources.map(t=>[t.id,t])));return textMaps.get(sources);}
 let armed='',symbolPreview=null,symbolDrag=null,linePreview=null,lineDrag=null,textPreview=null,textDrag=null,lineTool=false,textTool=false,lineStart=null,linePointer=null,viewScale=1,pan=null,paintFrame=null,transformPreview=null,transformDrag=null,searchResults=[],searchPosition=-1,searchLimit=30,searchBusy=false;
 const el=id=>document.getElementById(id);
 const clamp=(n,max)=>Math.max(0,Math.min(max,n));
 function previewDoc(before,id){return {...before,objects:before.objects.map(o=>o.id===id?clone(o):o)};}
 function interacting(){return !!(symbolDrag||lineDrag||textDrag||transformDrag||lineStart);}
 function requestDraw(){if(window.requestAnimationFrame){if(paintFrame===null)paintFrame=window.requestAnimationFrame(()=>{paintFrame=null;draw();});}else draw();}
 function selectedObject(doc=model.doc){const o=doc.objects.find(o=>o.id===selected)||(doc.pdf_lines||[]).find(o=>o.id===selected);if(o)return o;const text=(doc.pdf_texts||[]).find(o=>o.id===selected);return text?window.PDFText.editable(text):null;}
 function deselect(){
  for(const drag of [lineDrag,transformDrag])if(drag?.node?.hasPointerCapture?.(drag.pointerId))drag.node.releasePointerCapture(drag.pointerId);
  for(const node of [el('textMoveHandle'),symbolNodes.get(selected)])if(node?.hasPointerCapture?.(textDrag?.pointerId??symbolDrag?.pointerId))node.releasePointerCapture(textDrag?.pointerId??symbolDrag?.pointerId);
  symbolPreview=symbolDrag=linePreview=lineDrag=textPreview=textDrag=transformPreview=transformDrag=null;
  const stage=el('pdfEditorStage');if(linePointer!==null&&stage.hasPointerCapture?.(linePointer))stage.releasePointerCapture(linePointer);
  const old=selected,focused=document.activeElement;selected='';finishEditing();if([symbolNodes.get(old),lineNodes.get(old),el('textMoveHandle'),el('tRotate'),el('tScaleNW'),el('tScaleNE'),el('tScaleSW'),el('tScaleSE')].includes(focused))focused?.blur();window.getSelection?.()?.removeAllRanges();cancelInsertion();syncControls();resize();draw();
 }
 function updateTransformHandles(doc){
  const o=selectedObject(doc),show=!!o&&!o.deleted&&!!background&&!armed&&!lineTool&&!textTool,b=show?bounds(o):null;
  el('transformOutline').hidden=!show;if(show)Object.assign(el('transformOutline').style,{left:(b.x-5/viewScale)+'px',top:(b.y-5/viewScale)+'px',width:(b.w+10/viewScale)+'px',height:(b.h+10/viewScale)+'px'});
  const pad=12/viewScale;const positions=show?[[b.x-pad,b.y-pad],[b.x+b.w+pad,b.y-pad],[b.x-pad,b.y+b.h+pad],[b.x+b.w+pad,b.y+b.h+pad],[b.x+b.w/2,Math.max(0,b.y-43/viewScale)]]:[];
  ['tScaleNW','tScaleNE','tScaleSW','tScaleSE','tRotate'].forEach((id,i)=>{const node=el(id);node.hidden=!show;if(show)Object.assign(node.style,{left:positions[i][0]+'px',top:positions[i][1]+'px',width:((i===4?28:13)/viewScale)+'px',height:((i===4?28:13)/viewScale)+'px',fontSize:(21/viewScale)+'px'});});
 }
 function initTransforms(){
  if(!window.DrawingTransform)return;
  for(const id of ['tScaleNW','tScaleNE','tScaleSW','tScaleSE','tRotate']){
   const node=el(id),kind=id==='tRotate'?'rotate':'scale';
   node.onpointerdown=event=>{if(event.button!==0||!selected)return;event.preventDefault();event.stopPropagation();finishEditing();const o=selectedObject();if(!o)return;transformDrag={id:selected,kind,start:stagePoint(event),original:clone(o),before:model.doc,node,pointerId:event.pointerId};node.setPointerCapture(event.pointerId);};
   node.onpointermove=event=>{if(transformDrag?.node!==node||transformDrag.pointerId!==event.pointerId)return;event.preventDefault();try{const drag=transformDrag;transformPreview=previewDoc(drag.before,drag.id);let o=drag.original.type==='line'||drag.original.type==='path'?editLine(transformPreview,drag.id):drag.original.type==='text'?editObject(transformPreview,drag.id):transformPreview.objects.find(o=>o.id===drag.id);const transformed=window.DrawingTransform.apply(drag.original,kind,drag.start,stagePoint(event),event.shiftKey);Object.assign(o,transformed);requestDraw();}catch(error){symbolError(error);}};
   const finish=(event,cancel=false)=>{if(transformDrag?.node!==node||transformDrag.pointerId!==event.pointerId)return;const next=transformPreview;transformDrag=transformPreview=null;if(node.hasPointerCapture?.(event.pointerId))node.releasePointerCapture(event.pointerId);if(!cancel&&next){model.commit(next);changed();}else draw();syncControls();resize();};
   node.onpointerup=event=>finish(event);node.onpointercancel=event=>finish(event,true);
  }
 }

 function bounds(o){if(o.type==='symbol')return window.NetworkSymbols.bounds(o);if(o.type==='line'||o.type==='path')return window.PDFLines.bounds(o);if(o.type==='pen'){const xs=o.points.map(p=>p.x),ys=o.points.map(p=>p.y);return {x:Math.min(...xs),y:Math.min(...ys),w:Math.max(...xs)-Math.min(...xs),h:Math.max(...ys)-Math.min(...ys)};}if(o.type==='text')return window.PDFText.textBounds(o);return {x:Math.min(o.x1,o.x2),y:Math.min(o.y1,o.y2),w:Math.abs(o.x2-o.x1),h:Math.abs(o.y2-o.y1)};}
 function arrow(c,x1,y1,x2,y2,width){const angle=Math.atan2(y2-y1,x2-x1),size=Math.max(12,width*3);c.setLineDash([]);c.beginPath();c.moveTo(x2,y2);c.lineTo(x2-size*Math.cos(angle-.45),y2-size*Math.sin(angle-.45));c.moveTo(x2,y2);c.lineTo(x2-size*Math.cos(angle+.45),y2-size*Math.sin(angle+.45));c.stroke();}
 function render(target,doc,selection='',grid=false,pictures={original:background,clean:textBackground}){
  const background=pictures.original,textBackground=pictures.clean;
  target.save();target.clearRect(0,0,1200,800);target.fillStyle='#fff';target.fillRect(0,0,1200,800);
  if(background&&doc.background_ref){const ratio=Math.min(1200/background.width,800/background.height);target.drawImage(background,(1200-background.width*ratio)/2,(800-background.height*ratio)/2,background.width*ratio,background.height*ratio);}
  // Remove apenas as áreas dos textos alterados, recuperando as linhas e o fundo do PDF.
  // Todas as restaurações acontecem antes de desenhar os novos objetos.
  if(background&&textBackground&&doc.pdf_text_background_ref){
   const ratio=Math.min(1200/background.width,800/background.height),ox=(1200-background.width*ratio)/2,oy=(800-background.height*ratio)/2;
   const sources=sourceMap(doc.pdf_texts||[]);
   for(const object of doc.objects){const source=sources.get(object.pdf_text_id);if(!source)continue;const box=source.box;
    target.save();target.beginPath();target.rect(box.x,box.y,box.w,box.h);target.clip();target.drawImage(textBackground,ox,oy,background.width*ratio,background.height*ratio);target.restore();
   }
  }
  if(grid){target.strokeStyle='#edf1f4';target.lineWidth=1;target.beginPath();for(let x=0;x<=1200;x+=20){target.moveTo(x,0);target.lineTo(x,800);}for(let y=0;y<=800;y+=20){target.moveTo(0,y);target.lineTo(1200,y);}target.stroke();}
  for(const o of doc.objects){if(o.deleted)continue;target.save();target.strokeStyle=o.color;target.fillStyle=o.color;target.lineWidth=o.width;target.lineCap=o.line_cap||'round';target.lineJoin=o.line_join||'round';target.lineDashOffset=o.dash_offset||0;target.setLineDash(o.dash_array||(o.dash==='dashed'?[o.width*4,o.width*2]:o.dash==='dotted'?[1,o.width*2.5]:[]));target.beginPath();
   if(o.type==='symbol')window.NetworkSymbols.draw(target,o);
   if(o.type==='line'){target.moveTo(o.x1,o.y1);target.lineTo(o.x2,o.y2);target.stroke();if(o.arrow==='end'||o.arrow==='both')arrow(target,o.x1,o.y1,o.x2,o.y2,o.width);if(o.arrow==='both')arrow(target,o.x2,o.y2,o.x1,o.y1,o.width);}
   if(o.type==='path'){window.PDFLines.trace(target,o);target.stroke();}
   if((o.type==='line'||o.type==='path')&&o.label){const b=window.PDFLines.bounds(o);target.font='12px Arial';target.fillText(o.label,b.x+b.w/2,b.y+b.h/2-8);}
   if(o.type==='pen'){o.points.forEach((p,i)=>i?target.lineTo(p.x,p.y):target.moveTo(p.x,p.y));target.stroke();}
   if(o.type==='rect'){target.rect(o.x1,o.y1,o.x2-o.x1,o.y2-o.y1);target.stroke();}
   if(o.type==='ellipse'){target.ellipse((o.x1+o.x2)/2,(o.y1+o.y2)/2,Math.abs(o.x2-o.x1)/2,Math.abs(o.y2-o.y1)/2,0,0,2*Math.PI);target.stroke();}
   if(o.type==='text'){target.translate(o.x1,o.y1);target.rotate((o.rotation||0)*Math.PI/180);target.font=(o.italic?'italic ':'')+(o.bold?'bold ':'')+o.size+'px "'+(o.font||'Arial')+'"';String(o.text).split('\n').forEach((line,i)=>target.fillText(line,0,i*o.size*1.25));}
   target.restore();
   if(o.id===selection){const b=bounds(o);target.save();target.strokeStyle='#1879be';target.lineWidth=1;target.setLineDash([5,4]);target.strokeRect(b.x-7,b.y-7,b.w+14,b.h+14);target.restore();}
  }
  if(selection&&!doc.objects.some(o=>o.id===selection)){const source=(doc.pdf_texts||[]).find(t=>t.id===selection);if(source){const b=source.box;target.strokeStyle='#1879be';target.lineWidth=1.5;target.setLineDash([4,3]);target.strokeRect(b.x,b.y,b.w,b.h);}}
  target.restore();
 }
 function symbolError(error){el('symbolHint').textContent=error.message;}
 function selectedSymbol(doc=model.doc){return doc.objects.find(o=>o.id===selected&&o.type==='symbol');}
 function cancelInsertion(){const hadInsertion=armed||lineTool||textTool||linePreview;armed='';lineTool=false;textTool=false;lineStart=null;linePointer=null;linePreview=null;updateModes();if(hadInsertion)requestDraw();}
 function updateModes(){
  el('pdfEditorStage').classList.toggle('placing-item',!!armed||lineTool||textTool);el('dCancelInsert').hidden=!armed&&!lineTool&&!textTool;
  el('symbolHint').textContent=textTool?'Clique na página para inserir o texto. Esc cancela.':armed?'Clique na página para inserir: '+window.NetworkSymbols.get(armed).name+'. Esc cancela.':lineTool?(lineStart?'Clique no destino da linha. Shift alinha em 45°. Esc cancela.':'Clique e arraste ou marque as duas pontas da linha. Esc cancela.'):'Clique no texto para editar ou no símbolo/linha para selecionar. Arraste símbolos e linhas para mover.';
 }
 function palette(){
  const query=el('symbolSearch').value.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toUpperCase(),category=el('symbolGroup').value;
  const items=window.NetworkSymbols.all().filter(s=>(!category||s.group===category)&&(s.name+' '+s.tag).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toUpperCase().includes(query));
  const grid=el('symbolPalette');grid.replaceChildren();el('symbolCount').textContent=items.length+' símbolos';
  for(const item of items){
   const button=document.createElement('button');button.type='button';button.className='symbol-choice';button.title=item.name;button.setAttribute('aria-label','Inserir '+item.name);
   const preview=document.createElement('canvas');preview.width=92;preview.height=75;preview.setAttribute('aria-hidden','true');const body=window.NetworkSymbols.bodyBounds(item),size=Math.min(60,86/body.w*100,65/body.h*100);window.NetworkSymbols.draw(preview.getContext('2d'),{symbol_id:item.id,x1:46-(body.x+body.w/2)*size/100,y1:36-(body.y+body.h/2)*size/100,size,rotation:0,color:item.color||'#243c4c',width:2.8,status:'existente',label:''});
   const name=document.createElement('span');name.textContent=item.name;button.appendChild(preview);button.appendChild(name);
   button.onclick=()=>{finishEditing();cancelInsertion();selected='';armed=item.id;updateModes();syncControls();draw();el('pdfEditorViewport').scrollIntoView({block:'nearest'});};grid.appendChild(button);
  }
 }
 function syncSymbolControls(doc=model.doc){const o=selectedSymbol(doc);el('symbolControls').hidden=!o;if(!o)return;
  if(![...el('sType').children].some(option=>option.value===o.symbol_id)){const option=document.createElement('option');option.value=o.symbol_id;option.textContent=(o.symbol_definition?.name||'Símbolo')+' (do croqui)';el('sType').appendChild(option);}
  el('symbolSelected').textContent=o.symbol_definition?.name||window.NetworkSymbols.get(o.symbol_id)?.name||'Símbolo';
  for(const [field,key] of [['sType','symbol_id'],['sRotation','rotation'],['sColor','color'],['sStatus','status'],['sLabel','label'],['sX','x1'],['sY','y1']])if(document.activeElement!==el(field))el(field).value=o[key];
  if(document.activeElement!==el('sScale'))el('sScale').value=Math.round(o.size/70*1000)/10;el('sOpaque').checked=!!o.opaque;
 }
 function selectSymbol(id){finishEditing();selected=id;cancelInsertion();updateModes();syncControls();draw();}
 function updateSymbol(){const original=selectedSymbol();if(!original)return;
  try{const next=previewDoc(model.doc,selected),o=next.objects.find(o=>o.id===selected);Object.assign(o,{symbol_id:el('sType').value||original.symbol_id,size:Math.max(7,Math.min(700,(Number(el('sScale').value)||100)*.7)),rotation:Math.max(-360,Math.min(360,Number(el('sRotation').value)||0)),color:el('sColor').value,status:el('sStatus').value,label:el('sLabel').value.slice(0,96),x1:clamp(Number(el('sX').value)||0,1200),y1:clamp(Number(el('sY').value)||0,800),opaque:el('sOpaque').checked});
   if(o.symbol_id!==original.symbol_id){const definition=window.NetworkSymbols.get(o.symbol_id);if(o.symbol_id.startsWith('user_'))o.symbol_definition=clone(definition);else delete o.symbol_definition;}
   if(JSON.stringify(o)!==JSON.stringify(original)){model.commit(next);changed();}
  }catch(error){symbolError(error);}
 }
 function duplicateSymbol(){const o=selectedSymbol();if(!o)return;try{if(model.doc.objects.length>=1000)throw Error('Limite de 1.000 objetos atingido.');const next=previewDoc(model.doc,selected),copy={...clone(o),id:'sym_'+crypto.randomUUID().replaceAll('-',''),x1:clamp(o.x1+25,1200),y1:clamp(o.y1+25,800)};next.objects.push(copy);model.commit(next);selected=copy.id;changed();syncControls();symbolNodes.get(selected)?.focus();}catch(error){symbolError(error);}}
 function removeSymbol(){if(!selectedSymbol())return;const next=previewDoc(model.doc,selected);next.objects=next.objects.filter(o=>o.id!==selected);model.commit(next);selected='';changed();syncControls();}
 function stagePoint(event){const rect=el('pdfEditorStage').getBoundingClientRect();return {x:clamp((event.clientX-rect.left)*1200/rect.width,1200),y:clamp((event.clientY-rect.top)*800/rect.height,800)};}
 function placeSymbol(event){if(!armed||event.button!==0)return;event.preventDefault();event.stopPropagation();try{if(model.doc.objects.length>=1000)throw Error('Limite de 1.000 objetos atingido.');const p=stagePoint(event),o=window.NetworkSymbols.make(armed,p.x,p.y),next=previewDoc(model.doc,'');next.objects.push(o);model.commit(next);selected=o.id;armed='';changed();updateModes();syncControls();symbolNodes.get(selected)?.focus();}catch(error){symbolError(error);}}
 function moveSymbol(id,dx,dy){const next=previewDoc(model.doc,id),o=next.objects.find(o=>o.id===id);if(!o)return;o.x1=clamp(o.x1+dx,1200);o.y1=clamp(o.y1+dy,800);model.commit(next);changed();syncControls();}
 function updateSymbolLayer(doc,fast=false){const layer=el('symbolLayer'),alive=new Set(doc.objects.filter(o=>o.type==='symbol').map(o=>o.id));
  for(const [id,node] of symbolNodes)if(!fast&&!alive.has(id)){node.remove();symbolNodes.delete(id);}
  for(const o of doc.objects.filter(o=>o.type==='symbol'&&(!fast||o.id===selected))){let node=symbolNodes.get(o.id);
   if(!node){node=document.createElement('button');node.type='button';node.className='symbol-hit';node.dataset.symbolId=o.id;
    node.onfocus=()=>{if(selected!==o.id)selectSymbol(o.id);};
    node.onpointerdown=event=>{if(armed||lineTool||textTool||event.button!==0)return;event.preventDefault();event.stopPropagation();selectSymbol(o.id);node.focus();const current=selectedSymbol();symbolDrag={id:o.id,start:stagePoint(event),before:model.doc,x:current.x1,y:current.y1,pointerId:event.pointerId};node.setPointerCapture(event.pointerId);};
    node.onpointermove=event=>{if(symbolDrag?.id!==o.id)return;const p=stagePoint(event);symbolPreview=previewDoc(symbolDrag.before,symbolDrag.id);const item=symbolPreview.objects.find(x=>x.id===o.id);item.x1=clamp(symbolDrag.x+p.x-symbolDrag.start.x,1200);item.y1=clamp(symbolDrag.y+p.y-symbolDrag.start.y,800);requestDraw();};
    node.onpointerup=event=>{if(symbolDrag?.id!==o.id)return;const next=symbolPreview;symbolDrag=null;symbolPreview=null;if(node.hasPointerCapture?.(event.pointerId))node.releasePointerCapture(event.pointerId);if(next&&JSON.stringify(next.objects)!==JSON.stringify(model.doc.objects)){model.commit(next);changed();}else draw();syncControls();};
    node.onpointercancel=()=>{symbolPreview=null;symbolDrag=null;draw();syncControls();};
    node.onkeydown=event=>{const step=event.shiftKey?10:1;if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(event.key)){event.preventDefault();moveSymbol(o.id,event.key==='ArrowLeft'?-step:event.key==='ArrowRight'?step:0,event.key==='ArrowUp'?-step:event.key==='ArrowDown'?step:0);}else if(event.key==='Delete'||event.key==='Backspace'){event.preventDefault();removeSymbol();}else if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='d'){event.preventDefault();duplicateSymbol();}else if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='z'){event.preventDefault();history(event.shiftKey?'redo':'undo');}};
    layer.appendChild(node);symbolNodes.set(o.id,node);
   }
   const b=window.NetworkSymbols.bounds(o);Object.assign(node.style,{left:b.x+'px',top:b.y+'px',width:b.w+'px',height:b.h+'px'});node.classList.toggle('selected',o.id===selected);node.setAttribute('aria-label',(o.symbol_definition?.name||window.NetworkSymbols.get(o.symbol_id)?.name||'Símbolo')+' · '+window.NetworkSymbols.statusLabel[o.status]+(o.label?' · '+o.label:''));
  }
 }
 function linesIn(doc=model.doc){
  const modified=new Map(doc.objects.filter(o=>o.type==='line'||o.type==='path').map(o=>[o.id,o]));
  return [...(doc.pdf_lines||[]).map(o=>modified.get(o.id)||o),...doc.objects.filter(o=>(o.type==='line'||o.type==='path')&&!o.pdf_line_id)].filter(o=>!o.deleted);
 }
 function selectedLine(doc=model.doc){const o=doc.objects.find(o=>o.id===selected)||(doc.pdf_lines||[]).find(o=>o.id===selected);return o&&!o.deleted&&(o.type==='line'||o.type==='path')?o:null;}
 function editLine(doc,id){
  let o=doc.objects.find(o=>o.id===id);if(o)return o;
  const source=(doc.pdf_lines||[]).find(o=>o.id===id);if(!source)return null;
  if(doc.objects.length>=1000)throw Error('Limite de 1.000 alterações atingido.');o=window.PDFLines.editable(source);doc.objects.push(o);return o;
 }
 function selectLine(id){finishEditing();selected=id;cancelInsertion();syncControls();requestDraw();}
 function syncLineControls(doc=model.doc){const o=selectedLine(doc);el('lineControls').hidden=!o;if(!o)return;
  el('lineSelected').textContent=o.id.startsWith('pdfline_')?'Linha do PDF':'Linha adicionada';
  for(const [field,key] of [['lColor','color'],['lWidth','width'],['lDash','dash'],['lArrow','arrow'],['lLabel','label'],['lX1','x1'],['lY1','y1'],['lX2','x2'],['lY2','y2']])if(document.activeElement!==el(field))el(field).value=o[key]??'';
  const b=bounds(o);el('lX').value=b.x;el('lY').value=b.y;el('lineEndpoints').hidden=o.type!=='line';el('pathPosition').hidden=o.type==='line';el('lArrow').disabled=o.type!=='line';el('lRestore').disabled=!model.doc.objects.some(item=>item.id===o.id&&item.pdf_line_id);
 }
 function shiftLine(o,dx,dy){const b=bounds(o);return window.PDFLines.transform(o,[1,0,0,1,Math.max(-b.x,Math.min(1200-b.x-b.w,dx)),Math.max(-b.y,Math.min(800-b.y-b.h,dy))]);}
 function updateLine(){const original=selectedLine();if(!original)return;
  try{const next=previewDoc(model.doc,selected),o=editLine(next,selected);Object.assign(o,{color:el('lColor').value,width:Math.max(.1,Math.min(30,Number(el('lWidth').value)||.1)),dash:el('lDash').value,arrow:o.type==='line'?el('lArrow').value:'none',label:el('lLabel').value.slice(0,96)});
   if(o.dash!==original.dash){delete o.dash_array;delete o.dash_offset;}
   if(o.type==='line')for(const [field,key,max] of [['lX1','x1',1200],['lY1','y1',800],['lX2','x2',1200],['lY2','y2',800]])o[key]=clamp(Number(el(field).value)||0,max);
   else{const b=bounds(o);shiftLine(o,(Number(el('lX').value)||0)-b.x,(Number(el('lY').value)||0)-b.y);}
   model.commit(next);changed();syncLineControls();
  }catch(error){symbolError(error);}
 }
 function duplicateLine(){const current=selectedLine();if(!current)return;try{if(model.doc.objects.length>=1000)throw Error('Limite de 1.000 objetos atingido.');const copy=clone(current);delete copy.pdf_line_id;delete copy.operator_index;copy.id='line_'+crypto.randomUUID().replaceAll('-','');shiftLine(copy,25,25);const next=previewDoc(model.doc,selected);next.objects.push(copy);model.commit(next);selected=copy.id;changed();syncControls();lineNodes.get(selected)?.focus();}catch(error){symbolError(error);}}
 function removeLine(){if(!selectedLine())return;try{const next=previewDoc(model.doc,selected),o=editLine(next,selected);if(o.pdf_line_id)o.deleted=true;else next.objects=next.objects.filter(item=>item.id!==selected);model.commit(next);selected='';changed();syncControls();}catch(error){symbolError(error);}}
 function restoreLine(){const next=previewDoc(model.doc,selected);next.objects=next.objects.filter(o=>o.id!==selected||!o.pdf_line_id);model.commit(next);changed();syncControls();}
 function moveLine(id,dx,dy){try{const next=previewDoc(model.doc,id);shiftLine(editLine(next,id),dx,dy);model.commit(next);changed();syncControls();}catch(error){symbolError(error);}}
 function beginLineDrag(id,event,node,endpoint=null){
  if(armed||lineTool||textTool||event.button!==0)return;event.preventDefault();event.stopPropagation();selectLine(id);node.focus();
  lineDrag={id,start:stagePoint(event),before:model.doc,endpoint,node,pointerId:event.pointerId};node.setPointerCapture(event.pointerId);
 }
 function dragLine(event){if(!lineDrag||event.pointerId!==lineDrag.pointerId)return;event.preventDefault();const p=stagePoint(event),dx=p.x-lineDrag.start.x,dy=p.y-lineDrag.start.y;if(!dx&&!dy)return;
  try{linePreview=previewDoc(lineDrag.before,lineDrag.id);const o=editLine(linePreview,lineDrag.id);if(lineDrag.endpoint){o['x'+lineDrag.endpoint]=p.x;o['y'+lineDrag.endpoint]=p.y;}else shiftLine(o,dx,dy);requestDraw();}catch(error){linePreview=null;symbolError(error);}
 }
 function finishLineDrag(event,cancel=false){if(!lineDrag)return;if(event.pointerId!==undefined&&event.pointerId!==lineDrag.pointerId)return;
  const drag=lineDrag,next=linePreview;lineDrag=linePreview=null;if(drag.node.hasPointerCapture?.(drag.pointerId))drag.node.releasePointerCapture(drag.pointerId);
  if(!cancel&&next&&JSON.stringify(next.objects)!==JSON.stringify(model.doc.objects)){model.commit(next);changed();}else draw();syncControls();
 }
 function updateLineLayer(doc,fast=false){const values=fast?[selectedLine(doc)].filter(Boolean):linesIn(doc),alive=new Set(values.map(o=>o.id)),layer=el('lineLayer');
  for(const [id,node] of lineNodes)if(!fast&&!alive.has(id)){node.remove();lineNodes.delete(id);}
  for(const o of values){let node=lineNodes.get(o.id);
   if(!node){node=document.createElementNS('http://www.w3.org/2000/svg','path');node.setAttribute('class','line-hit');node.setAttribute('tabindex','0');node.setAttribute('role','button');node.dataset.lineId=o.id;
    node.onfocus=()=>{if(selected!==o.id)selectLine(o.id);};node.onpointerdown=event=>beginLineDrag(o.id,event,node);node.onpointermove=dragLine;node.onpointerup=event=>finishLineDrag(event);node.onpointercancel=event=>finishLineDrag(event,true);
    node.onkeydown=event=>{const step=event.shiftKey?10:1;if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(event.key)){event.preventDefault();moveLine(o.id,event.key==='ArrowLeft'?-step:event.key==='ArrowRight'?step:0,event.key==='ArrowUp'?-step:event.key==='ArrowDown'?step:0);}else if(['Delete','Backspace'].includes(event.key)){event.preventDefault();removeLine();}else if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='d'){event.preventDefault();duplicateLine();}else if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='z'){event.preventDefault();history(event.shiftKey?'redo':'undo');}};
    layer.appendChild(node);lineNodes.set(o.id,node);
   }
   if(node.lineObject!==o){if(!linePaths.has(o))linePaths.set(o,window.PDFLines.pathData(o));const data=linePaths.get(o);if(node.dataset.path!==data){node.setAttribute('d',data);node.dataset.path=data;}node.setAttribute('aria-label',(o.id.startsWith('pdfline_')?'Linha do PDF':'Linha adicionada')+(o.label?' · '+o.label:''));node.lineObject=o;}
   const width=Math.max(o.width+3,10/viewScale);if(node.hitWidth!==width){node.setAttribute('stroke-width',width);node.hitWidth=width;}
   if(node.isSelected!==(o.id===selected)){node.classList.toggle('selected',o.id===selected);node.isSelected=o.id===selected;}
  }
  const o=selectedLine(doc);for(const [id,end] of [['lHandleStart',1],['lHandleEnd',2]]){const handle=el(id);handle.hidden=!o||o.type!=='line';if(!handle.hidden)Object.assign(handle.style,{left:o['x'+end]+'px',top:o['y'+end]+'px',width:(12/viewScale)+'px',height:(12/viewScale)+'px'});}
  if(!fast)el('lineCount').textContent=(model.doc.pdf_lines?.length||0)+' traços reconhecidos no PDF · '+values.filter(o=>!o.id.startsWith('pdfline_')).length+' linhas adicionadas.';
 }
 function lineEnd(event){const p=stagePoint(event);if(!event.shiftKey)return p;const dx=p.x-lineStart.x,dy=p.y-lineStart.y,length=Math.hypot(dx,dy),angle=Math.round(Math.atan2(dy,dx)/(Math.PI/4))*Math.PI/4;return {x:clamp(lineStart.x+length*Math.cos(angle),1200),y:clamp(lineStart.y+length*Math.sin(angle),800)};}
 function previewNewLine(event){if(!lineTool||!lineStart||pan)return;const p=lineEnd(event);linePreview=previewDoc(model.doc,'');linePreview.objects.push({id:'line_preview',type:'line',x1:lineStart.x,y1:lineStart.y,x2:p.x,y2:p.y,width:2,color:'#183e53',dash:'solid',arrow:'none',label:''});requestDraw();}
 function commitNewLine(event){const p=lineEnd(event);if(Math.hypot(p.x-lineStart.x,p.y-lineStart.y)<.5)return false;
  if(model.doc.objects.length>=1000){symbolError(Error('Limite de 1.000 objetos atingido.'));return false;}
  const next=previewDoc(model.doc,selected),o={id:'line_'+crypto.randomUUID().replaceAll('-',''),type:'line',x1:lineStart.x,y1:lineStart.y,x2:p.x,y2:p.y,width:2,color:'#183e53',dash:'solid',arrow:'none',label:''};next.objects.push(o);model.commit(next);selected=o.id;cancelInsertion();changed();syncControls();lineNodes.get(selected)?.focus();return true;
 }
 function startNewLine(event){if(event.button!==0)return;event.preventDefault();event.stopPropagation();
  if(lineStart){commitNewLine(event);return;}lineStart=stagePoint(event);linePointer=event.pointerId;el('pdfEditorStage').setPointerCapture(event.pointerId);updateModes();
 }
 function initLines(){
  el('dNewLine').onclick=()=>{finishEditing();cancelInsertion();selected='';lineTool=true;updateModes();syncControls();draw();};
  el('lDuplicate').onclick=duplicateLine;el('lDelete').onclick=removeLine;el('lRestore').onclick=restoreLine;
  for(const id of ['lColor','lWidth','lDash','lArrow','lLabel','lX1','lY1','lX2','lY2','lX','lY'])el(id).onchange=updateLine;el('lLabel').oninput=updateLine;
  for(const [id,end] of [['lHandleStart',1],['lHandleEnd',2]]){const node=el(id);node.onpointerdown=event=>beginLineDrag(selected,event,node,end);node.onpointermove=dragLine;node.onpointerup=event=>finishLineDrag(event);node.onpointercancel=event=>finishLineDrag(event,true);}
  const stage=el('pdfEditorStage');stage.addEventListener('pointermove',previewNewLine);stage.addEventListener('pointerup',event=>{if(!lineTool||!lineStart||event.pointerId!==linePointer)return;linePointer=null;if(stage.hasPointerCapture?.(event.pointerId))stage.releasePointerCapture(event.pointerId);commitNewLine(event);});stage.addEventListener('pointercancel',()=>{if(lineTool)cancelInsertion();});
 }
 function refreshSymbols(){
  el('symbolGroup').replaceChildren();const all=document.createElement('option');all.value='';all.textContent='Todas as categorias';el('symbolGroup').appendChild(all);el('symbolGroup').value='';el('sType').replaceChildren();
  const list=window.NetworkSymbols.all(),groups=[...new Set(list.map(s=>s.group))];
  for(const value of groups){const option=document.createElement('option');option.value=value;option.textContent=value;el('symbolGroup').appendChild(option);}
  for(const item of list){const option=document.createElement('option');option.value=item.id;option.textContent=item.name;el('sType').appendChild(option);}
  palette();
 }
 function initSymbols(){
  refreshSymbols();
  el('dNewText').onclick=()=>{finishEditing();cancelInsertion();selected='';textTool=true;syncControls();updateModes();requestDraw();};el('dSymbolEditor').onclick=()=>openSymbolEditor(false);el('sEditDrawing').onclick=()=>openSymbolEditor(true);
  el('symbolSearch').oninput=palette;el('symbolGroup').onchange=palette;
  el('dCancelInsert').onclick=cancelInsertion;
  el('sDuplicate').onclick=duplicateSymbol;el('sDelete').onclick=removeSymbol;
  for(const field of ['sType','sScale','sRotation','sColor','sStatus','sLabel','sX','sY','sOpaque'])el(field).onchange=updateSymbol;el('sLabel').oninput=updateSymbol;
  el('pdfEditorStage').addEventListener('pointerdown',event=>{activity();if(textTool)placeText(event);else if(armed)placeSymbol(event);else if(lineTool)startNewLine(event);else if(event.button===0&&['pdfEditorStage','drawingCanvas','lineLayer','symbolLayer','pdfTextLayer','transformHandles','lineHandles'].includes(event.target?.id))deselect();},true);
  el('pdfEditorStage').addEventListener('keydown',event=>{if(event.key==='Escape'){event.preventDefault();event.stopPropagation();deselect();}});
  document.addEventListener?.('keydown',event=>{if(event.key==='Escape'&&!document.querySelector('dialog[open]')){event.preventDefault();deselect();}});
  palette();updateModes();
 }
 async function openSymbolEditor(editSelected){
  finishEditing();cancelInsertion();const object=editSelected?selectedSymbol():null,targetId=object?.id,pageId=currentPageId();
  const source=object?(object.symbol_definition||window.NetworkSymbols.get(object.symbol_id)):null;
  const onLibrarySaved=()=>{refreshSymbols();syncControls();draw();};
  try{await window.SymbolEditor.open(source,{onLibrarySaved,onSaved:definition=>{
   onLibrarySaved();if(!targetId||currentPageId()!==pageId||!window.NetworkSymbols.usable(definition))return;
   const target=model.doc.objects.find(o=>o.id===targetId);if(!target)return;
   const clean=clone(definition);delete clean.revision;delete clean.updated_at;
   if(JSON.stringify(target.symbol_definition)===JSON.stringify(clean))return;
   const next=previewDoc(model.doc,targetId),o=next.objects.find(o=>o.id===targetId);o.symbol_id=definition.id;o.symbol_definition=clean;model.commit(next);changed();syncControls();
  },onUse:id=>{if(targetId&&currentPageId()===pageId&&model.doc.objects.some(o=>o.id===targetId)){selectSymbol(targetId);}else{selected='';armed=id;updateModes();syncControls();draw();}}});}catch(error){symbolError(error);}
 }
 function placeText(event){
  if(event.button!==0)return;event.preventDefault();event.stopPropagation();
  if(!model.doc.background_ref){symbolError(Error('Importe a imagem ou o PDF antes de inserir o texto.'));cancelInsertion();return;}
  if(model.doc.objects.length>=1000){symbolError(Error('Limite de 1.000 alterações atingido.'));return;}
  const point=stagePoint(event),id='text_'+crypto.randomUUID().replaceAll('-','');
  const object={id,type:'text',x1:point.x,y1:point.y,text:'Novo texto',font:'Arial',size:22,color:'#111111',rotation:0,bold:false,italic:false,width:1,dash:'solid',arrow:'none'};
  cancelInsertion();model.commit({...model.doc,objects:model.doc.objects.concat([object])});selected=id;changed();syncControls();draw();
  const node=textNodes.get(id);node?.focus();if(node&&document.createRange&&window.getSelection){const range=document.createRange();range.selectNodeContents(node);const selection=window.getSelection();selection.removeAllRanges();selection.addRange(range);}
 }
 function setTextContent(){if(!selected)return;const next=previewDoc(model.doc,selected),object=editObject(next,selected);if(!object)return;object.text=el('dTextContent').value.slice(0,2000);delete object.text_width;model.commit(next);changed();}
 function sourceList(doc=model.doc){const added=doc.objects.filter(o=>o.type==='text'&&!o.pdf_text_id);return added.length?(doc.pdf_texts||[]).concat(added):doc.pdf_texts||[];}
 function currentText(source,doc=model.doc){return doc.objects.find(o=>o.id===source.id)||window.PDFText.editable(source);}
 function initTextMove(){
  const handle=el('textMoveHandle');
  handle.onpointerdown=event=>{if(event.button!==0)return;event.preventDefault();event.stopPropagation();finishEditing();const source=sourceList().find(t=>t.id===selected);if(!source)return;const o=currentText(source);textDrag={id:selected,start:stagePoint(event),before:model.doc,x:o.x1,y:o.y1,pointerId:event.pointerId};handle.setPointerCapture(event.pointerId);};
  handle.onpointermove=event=>{if(!textDrag||event.pointerId!==textDrag.pointerId)return;event.preventDefault();const p=stagePoint(event);try{textPreview=previewDoc(textDrag.before,textDrag.id);const o=editObject(textPreview,textDrag.id);o.x1=clamp(textDrag.x+p.x-textDrag.start.x,1200);o.y1=clamp(textDrag.y+p.y-textDrag.start.y,800);requestDraw();el('dX').value=Math.round(o.x1*10)/10;el('dY').value=Math.round(o.y1*10)/10;}catch(error){textPreview=null;el('drawingStatus').textContent=error.message;}};
  const finish=(event,cancel=false)=>{if(!textDrag||event.pointerId!==textDrag.pointerId)return;const next=textPreview;textDrag=textPreview=null;if(handle.hasPointerCapture?.(event.pointerId))handle.releasePointerCapture(event.pointerId);if(!cancel&&next&&JSON.stringify(next.objects)!==JSON.stringify(model.doc.objects)){model.commit(next);changed();}else draw();syncControls();};
  handle.onpointerup=event=>finish(event);handle.onpointercancel=event=>finish(event,true);
  handle.onkeydown=event=>{const step=event.shiftKey?10:1;if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(event.key))return;event.preventDefault();try{const next=previewDoc(model.doc,selected),o=editObject(next,selected);if(!o)return;o.x1=clamp(o.x1+(event.key==='ArrowLeft'?-step:event.key==='ArrowRight'?step:0),1200);o.y1=clamp(o.y1+(event.key==='ArrowUp'?-step:event.key==='ArrowDown'?step:0),800);model.commit(next);changed();syncControls();}catch(error){el('drawingStatus').textContent=error.message;}};
 }
 function fontCSS(o){return (o.italic?'italic ':'')+(o.bold?'bold ':'')+o.size+'px "'+(o.font||'Arial')+'"';}
 function baseline(o){const font=fontCSS(o);if(fontBaselines.has(font))return fontBaselines.get(font);ctx.save();ctx.font=font;const m=ctx.measureText('Mg');ctx.restore();const a=m.fontBoundingBoxAscent??o.size*.9,d=m.fontBoundingBoxDescent??o.size*.2,value=a+(o.size*1.25-a-d)/2;if(fontBaselines.size>512)fontBaselines.clear();fontBaselines.set(font,value);return value;}
 function metrics(o){if(textMetrics.has(o))return textMetrics.get(o);ctx.save();ctx.font=fontCSS(o);const width=o.text_width??Math.max(...String(o.text).split('\n').map(line=>ctx.measureText(line).width));ctx.restore();const value={width,offset:baseline(o)};textMetrics.set(o,value);return value;}
 function editObject(doc,ident){let o=doc.objects.find(o=>o.id===ident);if(o)return o;const source=sourceList().find(t=>t.id===ident);if(!source)return null;if(doc.objects.length>=1000)throw Error('Limite de 1.000 alterações atingido.');o=window.PDFText.editable(source);delete o.box;doc.objects.push(o);return o;}
 function syncControls(){const source=sourceList().find(t=>t.id===selected),o=source?currentText(source):null;
  if(el('dTextContent')){el('dTextContent').disabled=!o;if(document.activeElement!==el('dTextContent'))el('dTextContent').value=o?.text||'';}
  el('pdfSelectionLabel').textContent=source?'Texto selecionado: '+(o.text||source.text).slice(0,100):'Clique em um texto da página para editar.';
  for(const [key,field] of [['color','dColor'],['size','dSize'],['font','dFont'],['rotation','dRotation'],['x1','dX'],['y1','dY']]){el(field).disabled=!o;if(o)el(field).value=o[key]??(key==='font'?'Arial':0);}
  for(const [key,field] of [['bold','dBold'],['italic','dItalic']]){el(field).disabled=!o;el(field).checked=!!o?.[key];}el('textControls').hidden=!o;syncSymbolControls();syncLineControls();
 }
 function finishEditing(){if(active){const node=textNodes.get(active);active='';node?.blur();requestDraw();}}
 function selectText(ident,focus=false){selected=ident;syncControls();requestDraw();if(focus){const node=textNodes.get(ident);node?.focus();node?.scrollIntoView({block:'nearest',inline:'nearest'});}}
 function readInline(node){return (node.innerText??node.textContent??'').replace(/\r\n?/g,'\n').slice(0,2000);}
 function editInline(ident,node){
  const source=sourceList().find(t=>t.id===ident);if(!source)return;
  const text=readInline(node);if(text===currentText(source).text)return;
  try{const next=previewDoc(model.doc,ident),o=editObject(next,ident);o.text=text;delete o.text_width;model.commit(next);changed();}
  catch(error){node.textContent=currentText(source).text;el('drawingStatus').textContent=error.message;}
 }
 function pastePlain(event,node){
  event.preventDefault();const value=(event.clipboardData?.getData('text/plain')||'').slice(0,2000),selection=window.getSelection();
  if(!selection?.rangeCount)return;const range=selection.getRangeAt(0);if(!node.contains(range.commonAncestorContainer))return;
  range.deleteContents();const text=document.createTextNode(value);range.insertNode(text);range.setStartAfter(text);range.collapse(true);selection.removeAllRanges();selection.addRange(range);editInline(node.dataset.textId,node);
 }
 function updateTextLayer(doc=model.doc,fast=false){
  const layer=el('pdfTextLayer'),sources=sourceList(doc),modifiedTexts=new Map(doc.objects.filter(o=>o.type==='text').map(o=>[o.id,o])),alive=new Set(sources.map(t=>t.id)),query=el('dPdfSearch').value.trim().toLocaleLowerCase('pt-BR');
  for(const [id,node] of textNodes)if(!fast&&!alive.has(id)){node.remove();textNodes.delete(id);}
  let found=0;
  for(const source of (fast?sources.filter(t=>t.id===selected):sources)){
   const o=modifiedTexts.get(source.id)||editableText(source);let node=textNodes.get(source.id);
   if(!node){node=document.createElement('span');node.className='pdf-text-run';node.dataset.textId=source.id;node.contentEditable='plaintext-only';node.spellcheck=false;node.tabIndex=0;node.setAttribute('role','textbox');node.setAttribute('aria-multiline','true');node.setAttribute('aria-label','Editar texto do PDF: '+source.text.slice(0,100));
    node.onfocus=()=>{active=selected=source.id;cancelInsertion();updateModes();syncControls();requestDraw();};
    node.onblur=()=>{if(active===source.id)active='';requestDraw();};
    node.oninput=()=>editInline(source.id,node);node.onpaste=event=>pastePlain(event,node);
    node.onkeydown=event=>{if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='z'){event.preventDefault();history(event.shiftKey?'redo':'undo');}else if(event.key==='Escape'||((event.ctrlKey||event.metaKey)&&event.key==='Enter')){event.preventDefault();if(event.key==='Escape')deselect();else finishEditing();}};
    layer.appendChild(node);textNodes.set(source.id,node);
   }
   if(node.textObject===o&&node.isSelected===(selected===source.id)&&node.isEditing===(active===source.id)&&node.searchQuery===query){if(node.searchHit)found++;continue;}
   node.textObject=o;node.isSelected=selected===source.id;node.isEditing=active===source.id;node.searchQuery=query;
   if(active!==source.id&&node.textContent!==o.text)node.textContent=o.text;
   const hit=!!query&&(window.PDFSearch?window.PDFSearch.normalize(o.text):o.text.toLocaleLowerCase('pt-BR')).includes(window.PDFSearch?window.PDFSearch.normalize(query):query);if(hit)found++;
   node.searchHit=hit;node.classList.toggle('selected',selected===source.id);node.classList.toggle('editing',active===source.id);node.classList.toggle('search-match',hit);node.classList.toggle('deleted',!o.text);
   const {width,offset}=metrics(o),signature=JSON.stringify([o.x1,o.y1,o.size,o.rotation,o.font,o.bold,o.italic,o.color,width,active===source.id]);
   if(node.dataset.style!==signature){Object.assign(node.style,{left:o.x1+'px',top:(o.y1-offset)+'px',font:fontCSS(o),lineHeight:'1.25',minWidth:Math.max(12,width)+'px',minHeight:(o.size*1.25)+'px',transform:'rotate('+(o.rotation||0)+'deg)',transformOrigin:'0 '+offset+'px',color:active===source.id?o.color:'transparent',caretColor:o.color});node.dataset.style=signature;}
  }
  layer.hidden=!background;
  const source=sources.find(t=>t.id===selected),handle=el('textMoveHandle');handle.hidden=!source||!background;
  if(source){const o=currentText(source,doc),b=window.PDFText.textBounds(o);Object.assign(handle.style,{left:clamp(b.x,1200-32/viewScale)+'px',top:Math.max(0,b.y-30/viewScale)+'px',width:(28/viewScale)+'px',height:(26/viewScale)+'px',fontSize:(17/viewScale)+'px'});}
  if(fast)return;el('dPdfCount').textContent=query?found+' correspondência(s) em '+sources.length+' textos.':sources.length?sources.length+' textos editáveis na página.':'Nenhum texto selecionável reconhecido. Importe um PDF com texto selecionável.';
  el('pdfNoText').hidden=sources.length>0;
  el('pdfNoText').textContent=model.doc.background_ref?'Esta página é uma imagem ou não contém texto reconhecível. Importe o PDF original com texto selecionável.':'Importe o PDF do croqui para começar.';
 }
 function draw(){
  if(!ctx)return;
  const preview=transformPreview||textPreview||linePreview||symbolPreview||model.doc,fast=interacting();let displayed=preview;
  const resolution=Math.min(fast||navigating?1.5:5,Math.max(1,Math.ceil(viewScale*(window.devicePixelRatio||1)*2)/2));if(canvas.width!==Math.round(1200*resolution)||canvas.height!==Math.round(800*resolution)){canvas.width=Math.round(1200*resolution);canvas.height=Math.round(800*resolution);}
  if(active){displayed=previewDoc(displayed,active);const source=sourceList().find(t=>t.id===active);if(source){let o=displayed.objects.find(o=>o.id===active);if(!o){o=window.PDFText.editable(source);displayed.objects.push(o);}o.text='';}}
  ctx.save();ctx.scale(canvas.width/1200,canvas.height/800);ctx.imageSmoothingQuality='high';render(ctx,displayed,(selectedSymbol(displayed)||selectedLine(displayed))?selected:'');ctx.restore();updateTextLayer(preview,fast);updateSymbolLayer(displayed,fast);updateLineLayer(displayed,fast);updateTransformHandles(preview);el('dUndo').disabled=!model.undoStack.length;el('dRedo').disabled=!model.redoStack.length;
  el('dDelete').disabled=!sourceList().some(t=>t.id===selected);el('dRestoreText').disabled=!model.doc.objects.some(o=>o.id===selected&&o.pdf_text_id);el('dClear').disabled=!model.doc.objects.length;
  const source=model.doc.background_source;el('drawingBackground').textContent=model.doc.background_ref?(source?.name||'Croqui importado')+(source?.page?' · página '+source.page:''):'';
 }
 function resize(){
  const view=el('pdfEditorViewport');if(!view)return;
  viewScale=Math.max(.15,((view.clientWidth||1200)-2)/1200)*zoom;
  el('pdfEditorStage').style.transform='scale('+viewScale+')';el('pdfStageSpace').style.width=(1200*viewScale)+'px';el('pdfStageSpace').style.height=(800*viewScale)+'px';
  // A roda muda o enquadramento imediatamente; os pixels são refeitos uma vez por quadro.
  requestDraw();
 }
 function syncZoom(){
  const preset=[.25,.5,1,1.5,2,3,4,6,8].find(value=>Math.abs(value-zoom)<.00001),custom=el('dZoomCustom');
  custom.hidden=preset!==undefined;custom.value=String(zoom);custom.textContent=Math.round(zoom*100)+'%';el('dZoom').value=String(preset??zoom);
 }
 function setZoom(value,anchor){
  const view=el('pdfEditorViewport'),rect=view.getBoundingClientRect(),x=anchor?anchor.clientX-rect.left-(view.clientLeft||0):view.clientWidth/2,y=anchor?anchor.clientY-rect.top-(view.clientTop||0):view.clientHeight/2;
  const pointX=(view.scrollLeft+x)/viewScale,pointY=(view.scrollTop+y)/viewScale;
  activity();zoom=Math.max(.25,Math.min(8,value));resize();view.scrollLeft=Math.max(0,pointX*viewScale-x);view.scrollTop=Math.max(0,pointY*viewScale-y);syncZoom();
 }
 function endPan(){
  if(!pan)return;const pointerId=pan.pointerId,view=el('pdfEditorViewport');activity();pan=null;view.classList.toggle('panning',false);if(view.hasPointerCapture?.(pointerId))view.releasePointerCapture(pointerId);
 }
 function initNavigation(){
  const view=el('pdfEditorViewport');
  view.addEventListener('wheel',event=>{
   if(!event.deltaY)return;event.preventDefault();if(pan||interacting())return;
   const pixels=event.deltaY*(event.deltaMode===1?16:event.deltaMode===2?view.clientHeight:1);
   activity();navigating=true;clearTimeout(navigationTimer);navigationTimer=setTimeout(()=>{navigating=false;requestDraw();},180);
   setZoom(zoom*Math.exp(-Math.max(-200,Math.min(200,pixels))*.002),event);
  },{passive:false});
  view.addEventListener('pointerdown',event=>{
   if(event.button===0&&['pdfEditorViewport','pdfStageSpace'].includes(event.target?.id)){deselect();return;}
   if(event.button!==1||interacting())return;event.preventDefault();event.stopPropagation();finishEditing();
   activity();pan={pointerId:event.pointerId,x:event.clientX,y:event.clientY,left:view.scrollLeft,top:view.scrollTop};view.setPointerCapture(event.pointerId);view.classList.toggle('panning',true);
  },true);
  view.addEventListener('pointermove',event=>{if(!pan||event.pointerId!==pan.pointerId)return;event.preventDefault();event.stopPropagation();view.scrollLeft=pan.left-(event.clientX-pan.x);view.scrollTop=pan.top-(event.clientY-pan.y);},true);
  view.addEventListener('pointerup',event=>{if(!pan||event.pointerId!==pan.pointerId)return;event.preventDefault();event.stopPropagation();endPan();},true);
  view.addEventListener('pointercancel',endPan);view.addEventListener('lostpointercapture',endPan);
  for(const name of ['mousedown','auxclick'])view.addEventListener(name,event=>{if(event.button===1)event.preventDefault();});
  el('dZoom').onchange=()=>setZoom(Number(el('dZoom').value)||1);syncZoom();
 }
 function updateBackground(){
  const edited=new Set(model.doc.objects.map(o=>o.pdf_line_id).filter(Boolean)),excluded=(model.doc.pdf_lines||[]).filter(source=>edited.has(source.id)).map(source=>source.operator_index);
  const doc=model.doc,key=[doc.background_ref||'',doc.pdf_text_background_ref||'',doc.pdf_source_ref||'',excluded.join(',')].join('|');if(backgroundRef===key&&!backgroundError)return;
  if(backgroundRef?.split('|')[0]!==key.split('|')[0]){background=null;textBackground=null;}backgroundRef=key;backgroundError=null;callbacks?.onBackgroundStatus?.({loading:true,error:''});
  const read=ref=>ref?new Promise((resolve,reject)=>{const image=new Image();image.onload=()=>resolve(image);image.onerror=()=>reject(Error('Não foi possível carregar a imagem do croqui. Preserve ou restaure a pasta dados/media da obra. As edições continuam guardadas.'));image.src='/media/'+encodeURIComponent(ref);}):Promise.resolve(null);
  const fromPDF=preview=>window.PDFSource.render(doc.pdf_source_ref,doc.background_source,excluded,(doc.pdf_texts||[]).length>0,preview).then(p=>[p.original,p.clean]);
  const refs=[doc.background_ref||'',doc.pdf_text_background_ref||''].join('|');
  if(!assetPromise||assetKey!==refs){assetKey=refs;assetPromise=Promise.all([read(doc.background_ref),read(doc.pdf_text_background_ref)]);assetPromise.catch(()=>{if(assetKey===refs)assetPromise=null;});}
  const canonical=assetPromise.catch(error=>{
   if(!doc.pdf_source_ref||!window.PDFSource)throw error;
   // Reconstrói a imagem ausente a partir do PDF preservado, sem apagar edições.
   return window.PDFSource.render(doc.pdf_source_ref,doc.background_source,[],(doc.pdf_texts||[]).length>0,false).then(pictures=>[pictures.original,pictures.clean,true]).catch(()=>{throw Error('A imagem e o PDF original do croqui não puderam ser abertos. Restaure a pasta dados/media ou vincule o arquivo original. As edições continuam guardadas.');});
  });
  const request=canonical.then(pictures=>pictures[2]||!excluded.length?pictures:fromPDF(true));
  backgroundPromise=request.then(async([image,clean,recovered])=>{if(backgroundRef!==key)return;
   background=image;textBackground=clean;
   if(recovered&&callbacks?.onRecover){
    const refs=await callbacks.onRecover(image,clean);
    if(backgroundRef!==key)return;
    // Mantém as edições feitas enquanto a recuperação estava em andamento.
    assetKey='';assetPromise=null;backgroundRef=null;lastRendered='';model.commit({...model.doc,background_ref:refs.original,pdf_text_background_ref:refs.clean});changed();
   }
   if(backgroundRef===key){callbacks?.onBackgroundStatus?.({loading:false,error:''});if(!dirty&&el('drawingStatus'))el('drawingStatus').textContent=image?'Página carregada. Selecione textos, símbolos ou linhas para editar.':'Importe o PDF ou uma imagem do projeto.';}
   draw();resize();
  }).catch(error=>{if(backgroundRef===key){backgroundError=error;callbacks?.onBackgroundStatus?.({loading:false,error:error.message});if(el('drawingStatus'))el('drawingStatus').textContent=error.message;}});
 }
 function changed(){dirty=true;revision++;activity();loadedKey='';loadedDoc={...model.doc};updateBackground();callbacks?.onChange(loadedDoc);refreshSearch();requestDraw();el('drawingStatus').textContent='Salvando alterações do croqui…';scheduleImage();}
 function scheduleImage(){clearTimeout(timer);timer=setTimeout(autoFlush,IMAGE_IDLE_MS);}
 function busy(){return interacting()||pan||navigating||Date.now()-lastActivity<IMAGE_IDLE_MS;}
 function autoFlush(){if(!dirty)return;if(busy()){scheduleImage();return;}flush({automatic:true}).catch(error=>{el('drawingStatus').textContent='Edição guardada; imagem do croqui pendente: '+error.message;});}
 async function flush({automatic=false,allowMissing=false}={}){
  clearTimeout(timer);if(!callbacks||!canvas||!dirty)return;
  if(automatic&&busy()){scheduleImage();return;}
  if(inFlight){try{await inFlight;}catch(error){if(!allowMissing||!backgroundError)throw error;}return flush({automatic,allowMissing});}
  inFlight=(async()=>{let waiting;do{waiting=backgroundPromise;await waiting;}while(waiting!==backgroundPromise);if(!dirty||(automatic&&busy()))return;if(backgroundError){if(allowMissing)return;throw backgroundError;}
   const snapshot=model.doc,serial=revision,published=loadedDoc,signature=JSON.stringify(snapshot);if(signature===lastRendered){dirty=false;callbacks?.onUnchanged?.(published);el('drawingStatus').textContent='Alterações salvas automaticamente.';return;}
   const edited=new Set(snapshot.objects.map(o=>o.pdf_line_id).filter(Boolean)),excluded=(snapshot.pdf_lines||[]).filter(o=>edited.has(o.id)).map(o=>o.operator_index);
   const pdf=window.PDFSource,pictures=excluded.length?await (pdf.forExport||pdf.render)(snapshot.pdf_source_ref,snapshot.background_source,excluded,(snapshot.pdf_texts||[]).length>0):{original:background,clean:textBackground};
   try{
    if(automatic&&(revision!==serial||busy()))return;
    const data=await window.CroquiRender.png(snapshot,pictures);
    if(automatic&&(revision!==serial||busy()))return;
    await callbacks.onImage(data,signature,published);if(revision===serial){lastRendered=signature;dirty=false;el('drawingStatus').textContent='Alterações salvas automaticamente.';}
   }finally{if(excluded.length)pdf.release?.(pictures);}
  })().finally(()=>{inFlight=null;});await inFlight;if(allowMissing&&backgroundError)return;if(dirty){if(automatic)scheduleImage();else return flush();}
 }
 function load(doc,fallbackRef,needsImage=false){
  if(doc&&doc===loadedDoc&&!backgroundError){if(needsImage&&!dirty){dirty=true;lastRendered='';scheduleImage();}return;}
  const incoming=doc||{...blank(),background_ref:fallbackRef||null},key=JSON.stringify(incoming);if(key===loadedKey&&!backgroundError){loadedDoc=doc;if(needsImage&&!dirty){dirty=true;lastRendered='';scheduleImage();}return;}
  endPan();clearTimeout(navigationTimer);navigating=false;revision++;active=selected=armed='';symbolPreview=symbolDrag=linePreview=lineDrag=textPreview=textDrag=transformPreview=transformDrag=null;lineTool=false;textTool=false;lineStart=null;loadedKey=key;loadedDoc=doc;model=new DrawingModel(incoming);dirty=needsImage;lastRendered=needsImage?'':key;clearTimeout(timer);if(needsImage)scheduleImage();
  for(const node of textNodes.values())node.remove();textNodes.clear();for(const node of symbolNodes.values())node.remove();symbolNodes.clear();for(const node of lineNodes.values())node.remove();lineNodes.clear();updateBackground();refreshSearch();draw();if(ctx){syncControls();updateModes();zoom=1;resize();syncZoom();el('pdfEditorViewport').scrollLeft=el('pdfEditorViewport').scrollTop=0;}
 }
 function history(action){symbolPreview=symbolDrag=linePreview=lineDrag=textPreview=textDrag=transformPreview=transformDrag=null;lineTool=false;textTool=false;lineStart=null;armed='';finishEditing();if(model[action]()){if(!selectedSymbol()&&!selectedLine()&&!sourceList().some(t=>t.id===selected))selected='';changed();syncControls();updateModes();}}
 function updateSelected(){if(!selected)return;finishEditing();try{const next=previewDoc(model.doc,selected),o=editObject(next,selected);if(!o)return;
  Object.assign(o,{color:el('dColor').value,size:Math.max(2,Math.min(160,Number(el('dSize').value)||22)),font:el('dFont').value,rotation:clamp((Number(el('dRotation').value)||0)+360,720)-360,x1:clamp(Number(el('dX').value)||0,1200),y1:clamp(Number(el('dY').value)||0,800),bold:el('dBold').checked,italic:el('dItalic').checked});delete o.text_width;
  if(JSON.stringify(next.objects)!==JSON.stringify(model.doc.objects)){model.commit(next);changed();}syncControls();
 }catch(error){el('drawingStatus').textContent=error.message;}}
 function remove(){if(!selected)return;finishEditing();try{const next=previewDoc(model.doc,selected),o=editObject(next,selected);if(!o)return;if(o.pdf_text_id){o.text='';delete o.text_width;}else{next.objects=next.objects.filter(item=>item.id!==selected);selected='';}model.commit(next);changed();syncControls();}catch(error){el('drawingStatus').textContent=error.message;}}
 function restoreText(){finishEditing();const next=previewDoc(model.doc,selected);next.objects=next.objects.filter(o=>o.id!==selected||!o.pdf_text_id);model.commit(next);changed();syncControls();}
 function clear(){symbolPreview=symbolDrag=linePreview=lineDrag=textPreview=textDrag=transformPreview=transformDrag=null;lineTool=false;textTool=false;lineStart=null;armed='';finishEditing();if(!model.doc.objects.length)return;model.commit({...model.doc,objects:[]});selected='';changed();syncControls();updateModes();}
 async function setBackground(ref,source,pdf={}){await flush();endPan();finishEditing();model.commit({...blank(),background_ref:ref,background_source:source,pdf_text_background_ref:pdf.cleanRef||null,pdf_texts:pdf.texts||[],pdf_source_ref:pdf.pdfRef||null,pdf_lines:pdf.lines||[]});selected=armed='';symbolPreview=symbolDrag=linePreview=lineDrag=textPreview=textDrag=transformPreview=transformDrag=null;lineTool=false;textTool=false;lineStart=null;zoom=1;resize();syncZoom();el('pdfEditorViewport').scrollLeft=el('pdfEditorViewport').scrollTop=0;changed();syncControls();updateModes();await flush();}
 function searchPages(){return callbacks?.getPages?.()||[{id:'current',drawing:model.doc}];}
 function currentPageId(){return callbacks?.getPageId?.()||'current';}
 function refreshSearch(reset=false){
  if(!window.PDFSearch||!el('dPdfSearch'))return;
  const query=el('dPdfSearch').value,old=searchResults[searchPosition];
  searchResults=window.PDFSearch.find(searchPages(),query,currentPageId(),el('dSearchScope').value||'all');
  searchPosition=reset?-1:searchResults.findIndex(r=>r.pageId===old?.pageId&&r.objectId===old?.objectId);if(reset)searchLimit=30;
  el('pdfSearchPanel').hidden=!query.trim();el('pdfSearchCount').textContent=searchResults.length?(searchPosition>=0?(searchPosition+1)+' de ':'')+searchResults.length+' resultado(s).':'Nenhum resultado nos textos disponíveis.';
  el('dFindPrevious').disabled=el('dFind').disabled=!searchResults.length||searchBusy;
  const list=el('pdfSearchResults');list.replaceChildren();
  searchResults.slice(0,searchLimit).forEach((r,i)=>{const button=document.createElement('button');button.type='button';button.className='search-result';button.classList.toggle('current-result',i===searchPosition);button.textContent='Página '+(r.pageIndex+1)+(r.sourcePage?' (PDF '+r.sourcePage+')':'')+' · '+r.text.slice(0,180);button.title=r.sourceName;button.disabled=searchBusy;button.onclick=()=>openSearchResult(i);list.appendChild(button);});
  el('pdfSearchMore').hidden=searchResults.length<=searchLimit;
 }
 async function openSearchResult(index){
  if(searchBusy||!searchResults.length)return;const r=searchResults[(index+searchResults.length)%searchResults.length];searchBusy=true;refreshSearch();
  try{
   if(r.pageId!==currentPageId())await callbacks?.onSearchPage?.(r.pageId);
   if(r.pageId!==currentPageId())return;await backgroundPromise;if(r.pageId!==currentPageId())return;finishEditing();cancelInsertion();
   if(r.kind==='symbol')selectSymbol(r.objectId);else if(r.kind==='line'||r.kind==='path')selectLine(r.objectId);else selectText(r.objectId,true);
   (textNodes.get(r.objectId)||symbolNodes.get(r.objectId)||lineNodes.get(r.objectId))?.scrollIntoView({block:'center',inline:'center'});
   searchPosition=searchResults.findIndex(item=>item.pageId===r.pageId&&item.objectId===r.objectId);
  }catch(error){el('drawingStatus').textContent=error.message;}finally{searchBusy=false;refreshSearch();}
 }
 function findText(direction=1){refreshSearch();return openSearchResult(searchPosition<0?(direction===1?0:searchResults.length-1):searchPosition+direction);}
 function resetSearch(){if(el('dPdfSearch'))el('dPdfSearch').value='';searchResults=[];searchPosition=-1;refreshSearch();}
 function init(options){
  callbacks=options;const panel=document.querySelector('.drawing-panel');
  panel.innerHTML=window.DrawingUI();
  canvas=el('drawingCanvas');ctx=canvas.getContext('2d');el('dUndo').onclick=()=>history('undo');el('dRedo').onclick=()=>history('redo');el('dClear').onclick=clear;el('dDelete').onclick=remove;el('dRestoreText').onclick=restoreText;
  el('dPdfSearch').oninput=()=>{refreshSearch(true);draw();};el('dSearchScope').onchange=()=>refreshSearch(true);el('dFindPrevious').onclick=()=>findText(-1);el('pdfSearchMore').onclick=()=>{searchLimit+=30;refreshSearch();};el('dPdfSearch').onkeydown=event=>{if(event.key==='Enter'){event.preventDefault();findText();}};el('dFind').onclick=()=>findText();
  el('dTextContent').oninput=setTextContent;
  ['dFont','dSize','dColor','dX','dY','dRotation','dBold','dItalic'].forEach(id=>el(id).onchange=updateSelected);
  if(typeof ResizeObserver!=='undefined')new ResizeObserver(resize).observe(el('pdfEditorViewport'));else window.addEventListener?.('resize',resize);
  initSymbols();initLines();initTextMove();initTransforms();initNavigation();draw();syncControls();resize();
 }
 window.Drawing={init,load,flush,clear,setBackground,DrawingModel,bounds,render,deselect,resetSearch};
})();
