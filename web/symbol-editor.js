'use strict';
(() => {
 const copy=value=>JSON.parse(JSON.stringify(value));
 const uid=()=> 'user_'+crypto.randomUUID().replaceAll('-','');
 let dialog,doc=null,selected=-1,tool='select',gesture=null,undo=[],redo=[],timer,inFlight=null,dirty=false,options={},revision=0,view={x:-120,y:-120,size:240};
 const el=id=>document.getElementById(id),limit=(v,min=-100,max=100)=>Math.max(min,Math.min(max,Number(v)||0));
 function library(){const found=new Map(window.NetworkSymbols.all().map(s=>[s.id,s]));for(const s of window.NetworkSymbols.drafts())found.set(s.id,s);return [...found.values()];}
 function status(text){el('seStatus').textContent=text;}
 function snapshot(){return copy(doc);}
 function remember(before){undo.push(before);if(undo.length>60)undo.shift();redo=[];}
 function changed(before){if(before)remember(before);dirty=true;status('Salvando automaticamente…');clearTimeout(timer);timer=setTimeout(()=>flush().catch(error=>status(error.message+' Use Tentar novamente.')),700);paint();properties();}
 async function flush(){
  clearTimeout(timer);if(inFlight){await inFlight;return flush();}if(!doc||!dirty)return;
  const saved=snapshot(),signature=JSON.stringify(saved);
  inFlight=(async()=>{const result=await api('/api/custom-symbols',{symbol:saved,expected_revision:revision});revision=result.revision;window.NetworkSymbols.upsert(result);if(JSON.stringify(doc)===signature)dirty=false;options.onSaved?.(result);status(window.NetworkSymbols.usable(result)?'Simbologia salva automaticamente.':'Rascunho salvo. Adicione um nome e pelo menos um elemento para inserir.');})().finally(()=>{inFlight=null;});
  await inFlight;if(dirty)return flush();
 }
 function position(event){const rect=el('seCanvas').getBoundingClientRect();return {x:limit((event.clientX-rect.left)/rect.width*view.size+view.x),y:limit((event.clientY-rect.top)/rect.height*view.size+view.y)};}
 function translate(op,dx,dy){
  const value=copy(op);
  if(value[0]==='poly'){value[1]=value[1].map(([x,y])=>[limit(x+dx),limit(y+dy)]);}
  else{value[1]=limit(value[1]+dx);value[2]=limit(value[2]+dy);if(value[0]==='line'){value[3]=limit(value[3]+dx);value[4]=limit(value[4]+dy);}}
  return value;
 }
 function box(op){const [kind,...v]=op;
  if(kind==='line')return {x:Math.min(v[0],v[2]),y:Math.min(v[1],v[3]),w:Math.abs(v[2]-v[0]),h:Math.abs(v[3]-v[1])};
  if(kind==='circle'||kind==='arc')return {x:v[0]-v[2],y:v[1]-v[2],w:v[2]*2,h:v[2]*2};
  if(kind==='rect')return {x:v[0],y:v[1],w:v[2],h:v[3]};
  if(kind==='poly'){const xs=v[0].map(p=>p[0]),ys=v[0].map(p=>p[1]);return {x:Math.min(...xs),y:Math.min(...ys),w:Math.max(...xs)-Math.min(...xs),h:Math.max(...ys)-Math.min(...ys)};}
  return {x:v[0]-Math.min(90,v[2].length*v[3]*.55)/2,y:v[1]-v[3],w:Math.min(90,v[2].length*v[3]*.55),h:v[3]*1.2};
 }
 function hit(p){for(let i=doc.ops.length-1;i>=0;i--){const b=box(doc.ops[i]);if(p.x>=b.x-4&&p.x<=b.x+b.w+4&&p.y>=b.y-4&&p.y<=b.y+b.h+4)return i;}return -1;}
 function paint(){
  if(!doc)return;const canvas=el('seCanvas'),ctx=canvas.getContext('2d');ctx.clearRect(0,0,480,480);ctx.fillStyle='#fff';ctx.fillRect(0,0,480,480);if(!gesture){const b=window.NetworkSymbols.bodyBounds(doc),size=Math.max(240,b.w+40,b.h+40);view={x:b.x+b.w/2-size/2,y:b.y+b.h/2-size/2,size};}ctx.save();ctx.scale(480/view.size,480/view.size);ctx.translate(-view.x,-view.y);
  ctx.lineWidth=.5;ctx.strokeStyle='#e8edf2';ctx.beginPath();for(let n=Math.floor(Math.min(view.x,view.y)/10)*10;n<=Math.max(view.x,view.y)+view.size;n+=10){ctx.moveTo(n,view.y);ctx.lineTo(n,view.y+view.size);ctx.moveTo(view.x,n);ctx.lineTo(view.x+view.size,n);}ctx.stroke();ctx.strokeStyle='#b2c8d6';ctx.strokeRect(-50,-50,100,100);
  window.NetworkSymbols.draw(ctx,{symbol_id:doc.id,symbol_definition:doc,x1:0,y1:0,size:100,color:doc.color,width:2.5,status:'existente',label:''});
  if(doc.ops[selected]){const b=box(doc.ops[selected]);ctx.strokeStyle='#087db9';ctx.setLineDash([2,2]);ctx.lineWidth=1;ctx.strokeRect(b.x-3,b.y-3,b.w+6,b.h+6);}ctx.restore();
  el('seUndo').disabled=!undo.length;el('seRedo').disabled=!redo.length;el('seDelete').disabled=selected<0;el('seUse').disabled=!window.NetworkSymbols.usable(doc);
 }
 const labels={line:'Linha',circle:'Círculo',rect:'Retângulo',text:'Texto',poly:'Polígono',arc:'Arco'};
 function properties(){
  const list=el('seElements');list.replaceChildren();doc.ops.forEach((op,index)=>{const option=document.createElement('option');option.value=index;option.textContent=(index+1)+' · '+labels[op[0]]+(op[0]==='text'?' · '+op[3]:'');list.appendChild(option);});list.value=selected>=0?String(selected):'';
  const node=el('seProperties');node.replaceChildren();const op=doc.ops[selected];if(!op)return;
  function field(label,index,type='number',min=-100,max=100){const wrap=document.createElement('label'),input=document.createElement('input');wrap.textContent=label;input.type=type;input.value=op[index];if(type==='number'){input.min=min;input.max=max;input.step='.5';}else input.maxLength=32;input.oninput=()=>{const before=snapshot();doc.ops[selected][index]=type==='number'?limit(input.value,min,max):input.value.slice(0,32);remember(before);dirty=true;status('Salvando automaticamente…');clearTimeout(timer);timer=setTimeout(()=>flush().catch(e=>status(e.message)),700);paint();};wrap.appendChild(input);node.appendChild(wrap);}
  if(op[0]==='poly'){
   const label=document.createElement('label'),input=document.createElement('textarea');label.textContent='Pontos (x,y; x,y; …)';input.value=op[1].map(p=>p.join(',')).join('; ');input.onchange=()=>{try{const points=input.value.split(';').map(part=>part.trim().split(',').map(Number));if(points.length<2||points.length>200||points.some(p=>p.length!==2||p.some(v=>!Number.isFinite(v)||Math.abs(v)>100)))throw Error('Use de 2 a 200 pares x,y entre -100 e 100.');const before=snapshot();doc.ops[selected][1]=points;changed(before);}catch(e){status(e.message);}};label.appendChild(input);node.appendChild(label);
  }else{field('X',1);field('Y',2);}
  if(op[0]==='line'){field('X final',3);field('Y final',4);}
  if(op[0]==='rect'){field('Largura',3,'number',.1,200);field('Altura',4,'number',.1,200);}
  if(op[0]==='circle'||op[0]==='arc')field('Raio',3,'number',.1,100);
  if(op[0]==='arc'){field('Ângulo inicial',4,'number',-360,360);field('Ângulo final',5,'number',-360,360);}
  if(op[0]==='text'){field('Texto',3,'text');field('Tamanho',4,'number',2,60);}
  if(['rect','circle','poly'].includes(op[0])){const index=op.length-1,wrap=document.createElement('label'),input=document.createElement('select');for(const [value,name] of [['false','Vazio'],['true','Preenchido'],['projetado','Preencher ao instalar']]){const option=document.createElement('option');option.value=value;option.textContent=name;input.appendChild(option);}input.value=String(op[index]);input.onchange=()=>{const before=snapshot();doc.ops[selected][index]=input.value==='projetado'?'projetado':input.value==='true';changed(before);};wrap.textContent='Preenchimento';wrap.appendChild(input);node.appendChild(wrap);}
 }
 function fields(){el('seName').value=doc.name;el('seTag').value=doc.tag;el('seColor').value=doc.color;paint();properties();}
 function templates(){const select=el('seTemplate');select.replaceChildren();const empty=document.createElement('option');empty.value='';empty.textContent='Escolha uma simbologia para editar…';select.appendChild(empty);for(const item of library()){const option=document.createElement('option');option.value=item.id;option.textContent=(item.id.startsWith('user_')?'Minha · ':'Modelo · ')+(item.name||'Rascunho sem nome');select.appendChild(option);}}
 function setDoc(source){
  const personal=source?.id?.startsWith('user_');revision=personal?(source.revision||0):0;doc=source?copy(source):{name:'Nova simbologia',tag:'',color:'#243c4c',ops:[]};
  if(!personal){doc.id=uid();if(source)doc.name=(source.name+' (personalizada)').slice(0,96);}
  doc.group='Minhas simbologias';doc.color=doc.color||'#243c4c';doc.tag=doc.tag||'';delete doc.revision;delete doc.updated_at;selected=-1;undo=[];redo=[];dirty=false;templates();el('seTemplate').value=personal?doc.id:'';fields();status('Alterações salvas automaticamente. Modelos da rede geram uma cópia pessoal.');
 }
 function create(){
  dialog=document.createElement('dialog');dialog.id='symbolEditorDialog';dialog.className='symbol-editor-dialog';dialog.innerHTML=`<div class="symbol-editor-heading"><div><h2>Criar ou editar simbologia</h2><p>Desenhe elementos, ajuste as medidas e arraste para reposicionar. Os modelos da rede geram uma cópia.</p></div><button id="seClose" class="secondary">Fechar</button></div><div class="symbol-editor-fields"><label>Simbologia existente<select id="seTemplate"></select></label><button id="seNew" class="secondary">Nova simbologia</button><button id="seCopy" class="secondary">Criar cópia</button><label>Nome<input id="seName" maxlength="96"></label><label>Legenda padrão<input id="seTag" maxlength="32"></label><label>Cor<input id="seColor" type="color"></label></div><div class="symbol-editor-body"><div><div class="symbol-editor-tools"><label>Ferramenta<select id="seTool"><option value="select">Selecionar / mover</option><option value="line">Linha</option><option value="rect">Retângulo</option><option value="circle">Círculo</option><option value="text">Texto</option></select></label><button id="seUndo" class="secondary">Desfazer</button><button id="seRedo" class="secondary">Refazer</button><button id="seDelete" class="secondary">Excluir elemento</button></div><canvas id="seCanvas" width="480" height="480" aria-label="Área de criação da simbologia"></canvas><small>Grade: 10 unidades. Contorno central: tamanho padrão de 100 × 100.</small></div><aside><label>Elementos<select id="seElements" size="8"></select></label><div id="seProperties" class="property-grid"></div></aside></div><p id="seStatus" role="status"></p><p class="muted">A edição é aplicada ao símbolo selecionado e às próximas inserções. Outros símbolos já colocados mantêm seu desenho.</p><div class="actions"><button id="seRetry" class="secondary">Tentar novamente</button><button id="seUse" class="primary">Usar no croqui</button></div>`;
  document.body.appendChild(dialog);
  const safe=fn=>async()=>{try{await fn();}catch(error){status(error.message);}};
  const close=safe(async()=>{await flush();dialog.close();});el('seClose').onclick=close;dialog.oncancel=event=>{event.preventDefault();if(gesture){const pointer=gesture.pointerId;doc=gesture.before;gesture=null;const canvas=el('seCanvas');if(canvas.hasPointerCapture(pointer))canvas.releasePointerCapture(pointer);paint();properties();}else close();};
  el('seNew').onclick=safe(async()=>{await flush();options={...options,onSaved:options.onLibrarySaved||options.onSaved};setDoc();});
  el('seCopy').onclick=safe(async()=>{if(inFlight)try{await inFlight;}catch{}clearTimeout(timer);const source=snapshot();source.id='template';options={...options,onSaved:options.onLibrarySaved||options.onSaved};setDoc(source);doc.name=(source.name+' (cópia)').slice(0,96);fields();dirty=true;await flush();});
  el('seTemplate').onchange=safe(async()=>{const value=el('seTemplate').value;await flush();const source=library().find(s=>s.id===value);if(source)setDoc(source);});
  el('seUse').onclick=safe(async()=>{if(!window.NetworkSymbols.usable(doc))throw Error('Adicione um nome e um elemento à simbologia.');dirty=true;await flush();const id=doc.id;dialog.close();options.onUse?.(id);});
  el('seRetry').onclick=safe(flush);
  for(const [id,key] of [['seName','name'],['seTag','tag'],['seColor','color']])el(id).oninput=()=>{const before=snapshot();doc[key]=el(id).value;changed(before);};
  el('seTool').onchange=()=>{tool=el('seTool').value;};el('seElements').onchange=()=>{selected=Number(el('seElements').value);paint();properties();};
  el('seDelete').onclick=()=>{if(selected<0)return;const before=snapshot();doc.ops.splice(selected,1);selected=-1;changed(before);};
  el('seUndo').onclick=()=>{if(!undo.length)return;redo.push(snapshot());doc=undo.pop();selected=-1;changed();fields();};el('seRedo').onclick=()=>{if(!redo.length)return;undo.push(snapshot());doc=redo.pop();selected=-1;changed();fields();};
  const canvas=el('seCanvas');
  canvas.onpointerdown=event=>{if(event.button!==0)return;event.preventDefault();clearTimeout(timer);const start=position(event),before=snapshot();if(tool==='select'){selected=hit(start);if(selected<0){paint();properties();return;}}
   else{if(doc.ops.length>=200){status('Limite de 200 elementos atingido.');return;}const value=tool==='line'?['line',start.x,start.y,start.x,start.y]:tool==='rect'?['rect',start.x,start.y,1,1,false]:tool==='circle'?['circle',start.x,start.y,1,false]:['text',start.x,start.y,'Texto',18];doc.ops.push(value);selected=doc.ops.length-1;}
   gesture={before,start,index:selected,pointerId:event.pointerId,op:copy(doc.ops[selected])};canvas.setPointerCapture(event.pointerId);paint();properties();};
  canvas.onpointermove=event=>{if(!gesture||gesture.pointerId!==event.pointerId)return;const p=position(event),g=gesture,dx=p.x-g.start.x,dy=p.y-g.start.y;
   if(tool==='select'||tool==='text')doc.ops[g.index]=translate(g.op,dx,dy);
   else if(tool==='line')doc.ops[g.index]=['line',g.start.x,g.start.y,p.x,p.y];
   else if(tool==='rect')doc.ops[g.index]=['rect',Math.min(g.start.x,p.x),Math.min(g.start.y,p.y),Math.max(.1,Math.abs(dx)),Math.max(.1,Math.abs(dy)),false];
   else doc.ops[g.index]=['circle',g.start.x,g.start.y,Math.max(.1,Math.min(100,Math.hypot(dx,dy))),false];paint();};
  const end=(event,cancel=false)=>{if(!gesture||gesture.pointerId!==event.pointerId)return;const before=gesture.before;gesture=null;if(canvas.hasPointerCapture(event.pointerId))canvas.releasePointerCapture(event.pointerId);if(cancel){doc=before;paint();properties();}else changed(before);};canvas.onpointerup=event=>end(event);canvas.onpointercancel=event=>end(event,true);
 }
 async function open(source,callbacks={}){
  if(!dialog)create();await flush();options=callbacks;
  try{window.NetworkSymbols.setCustom(await api('/api/custom-symbols'));}catch(error){/* A cópia já carregada continua disponível e a próxima gravação informa falhas. */}
  if(source?.id?.startsWith('user_'))source={...source,revision:window.NetworkSymbols.drafts().find(s=>s.id===source.id)?.revision||0};
  tool='select';el('seTool').value=tool;setDoc(source);dialog.showModal();
 }
 window.SymbolEditor={open,flush,box,translate};
})();
