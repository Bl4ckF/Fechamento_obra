'use strict';
(() => {
 const host=$('tab-map');let selected=null,results=[],timer,request=0,owner=null,view=null,drag=null;
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 host.innerHTML=`<div class="page-heading"><div><p class="eyebrow">LOCALIZAÇÃO DA OBRA</p><h1>Endereços e Google Earth</h1><p>Localize um endereço ou importe pontos, linhas e áreas de um arquivo KML/KMZ.</p></div></div>
 <section class="card padded"><label>Endereço, cidade ou coordenada<input id="addressQuery" maxlength="200" autocomplete="off" placeholder="Ex.: Avenida Afonso Pena, Campo Grande, MS"></label><p class="muted">Ao digitar 4 caracteres, o endereço é enviado ao Photon/OpenStreetMap. Sugestões aproximadas: confira antes de aplicar. A busca precisa de internet; coordenadas e KML/KMZ funcionam offline.</p><div id="addressStatus" role="status" aria-live="polite"></div><div id="addressResults" class="geo-results"></div><small>Endereços: Photon · © colaboradores OpenStreetMap.</small></section>
 <section class="card padded section-spacer"><h2>Coordenada do local</h2><label>Cole a coordenada completa<input id="coordinateInput" maxlength="500" placeholder="21K 753302 7725693"></label><p class="muted">UTM com faixa: 21K 753302 7725693 · UTM com hemisfério: 21 SUL 753302 7725693 · Decimal: -20.47, -54.62 · DMS: 20°28′12″S 54°37′12″W · Graus/minutos: 20°28.2′S 54°37.2′W. Referência WGS84; não converte outros datums automaticamente.</p><details><summary>Informar latitude e longitude separadamente</summary><div class="settings-grid"><label>Latitude decimal<input id="locationLat" inputmode="decimal"></label><label>Longitude decimal<input id="locationLon" inputmode="decimal"></label></div></details><div class="actions"><button id="convertLocation" class="secondary">Conferir coordenada</button><button id="useLocation" class="primary" disabled>Aplicar ao ponto atual</button><button id="newLocationPoint" class="secondary" disabled>Criar ponto neste local</button><a id="externalLocation" class="secondary link-button" target="_blank" rel="noopener noreferrer" hidden>Conferir no mapa online</a></div><p id="coordinateFormats"></p><p id="locationUTM" role="status">Selecione um resultado ou informe as coordenadas.</p></section>
 <section class="card padded section-spacer"><h2>Projeto do Google Earth</h2><p>O Google Earth Web precisa abrir em uma janela própria: o serviço bloqueia sua incorporação nesta página. Exporte o projeto como KML/KMZ para usá-lo no book.</p><a id="openGoogleEarth" class="secondary link-button" href="https://earth.google.com/web/" target="_blank" rel="noopener noreferrer">Abrir Google Earth</a><label>Arquivo KML ou KMZ (até 10 MB)<input id="earthFile" type="file" accept=".kml,.kmz"></label><p class="muted">No Google Earth, salve/exporte os elementos como KML ou KMZ. Pontos, linhas e áreas são preservados na obra; não criam serviços ou materiais automaticamente.</p><div id="earthStatus" role="status"></div><div class="actions"><button id="fitGeography" class="secondary">Enquadrar projeto</button><button id="geographyToCroqui" class="secondary">Adicionar prévia ao croqui</button></div><p class="muted">Prévia geográfica sem imagem de fundo. Clique para escolher uma coordenada. Role para ampliar; arraste para navegar. Azul: projeto importado. Verde: pontos da obra.</p><svg id="geographyPreview" viewBox="0 0 800 400" preserveAspectRatio="none" role="img" aria-label="Prévia de pontos, linhas e áreas" style="width:100%;height:400px;background:#edf3f5;border:1px solid #ccd8dd;touch-action:none"></svg><div id="earthFeatures"></div></section>`;
 const status=(id,msg)=>$(id).textContent=msg;
 const project=([lon,lat])=>[lon,-Math.log(Math.tan(Math.PI/4+lat*Math.PI/360))*180/Math.PI];
 const inverse=([x,y])=>({lon:x,lat:(2*Math.atan(Math.exp(-y*Math.PI/180))-Math.PI/2)*180/Math.PI});
 const allCoords=f=>f.type==='Point'?[f.coordinates]:f.type==='LineString'?f.coordinates:f.coordinates.flat();
 function points(){return (Book.summary().points||[]).filter(p=>Number.isFinite(p.lat)&&Number.isFinite(p.lon));}
 function fit(){
  const coords=[...(Book.summary().geography||[]).flatMap(allCoords),...points().map(p=>[p.lon,p.lat])];if(selected)coords.push([selected.lon,selected.lat]);
  if(!coords.length)coords.push([-54.62,-20.47]);
  const projected=coords.map(project);let minX=Infinity,maxX=-Infinity,minY=Infinity,maxY=-Infinity;
  for(const [x,y] of projected){minX=Math.min(x,minX);maxX=Math.max(x,maxX);minY=Math.min(y,minY);maxY=Math.max(y,maxY);}
  const w=Math.max(.005,(maxX-minX)*1.25,(maxY-minY)*2.5);view=[(minX+maxX)/2-w/2,(minY+maxY)/2-w/4,w,w/2];draw();
 }
 function draw(){
  if(!view)return;const svg=$('geographyPreview'),[x,y,w,h]=view,scale=w/800;
  svg.setAttribute('viewBox',view.join(' '));let html='';
  for(const f of Book.summary().geography||[]){
   if(f.type==='Point'){const [a,b]=project(f.coordinates);html+=`<circle cx="${a}" cy="${b}" r="${5*scale}" fill="#176fa1"><title>${esc(f.name)}</title></circle>`;}
   else{const rings=f.type==='Polygon'?f.coordinates:[f.coordinates];const d=rings.map(r=>r.map((p,i)=>(i?'L':'M')+project(p).join(' ')).join(' ')+(f.type==='Polygon'?' Z':'')).join(' ');html+=`<path d="${d}" fill="${f.type==='Polygon'?'#338fc333':'none'}" fill-rule="evenodd" stroke="#176fa1" stroke-width="${2*scale}"><title>${esc(f.name)}</title></path>`;}
  }
  for(const p of points()){const [a,b]=project([p.lon,p.lat]);html+=`<circle cx="${a}" cy="${b}" r="${5*scale}" fill="#148449"/><text x="${a+7*scale}" y="${b}" font-size="${12*scale}">${esc(p.number)}</text>`;}
  if(selected){const [a,b]=project([selected.lon,selected.lat]);html+=`<circle cx="${a}" cy="${b}" r="${7*scale}" fill="#c74823" stroke="white" stroke-width="${2*scale}"/>`;}
  svg.innerHTML=html;
 }
 function refresh(){
  const current=Book.summary();if(current!==owner){owner=current;selected=null;view=null;request++;results=[];$('addressResults').replaceChildren();$('locationLat').value='';$('locationLon').value='';$('coordinateInput').value='';status('coordinateFormats','');status('locationUTM','Selecione uma localização.');$('useLocation').disabled=$('newLocationPoint').disabled=true;$('externalLocation').hidden=true;}
  $('earthFeatures').innerHTML=(current.geography||[]).map((f,i)=>`<div class="card padded section-spacer"><strong>${esc(f.name)}</strong> · ${esc({Point:'Ponto',LineString:'Linha',Polygon:'Área'}[f.type])}<small> · ${allCoords(f).length} vértices · ${esc(f.source)}</small><div class="actions"><button data-geofocus="${i}" class="secondary">Ver / selecionar início</button><button data-georemove="${i}" class="secondary">Remover elemento importado</button></div></div>`).join('');
  if(!view)fit();else draw();
 }
 async function select(lat,lon,refit=true,raw=null){
  const current=Book.summary(),ticket=++request;
  const data=await api('/api/coordinate?q='+encodeURIComponent(raw??(lat+', '+lon)));
  if(current!==Book.summary()||ticket!==request)return;
  selected=data;$('coordinateInput').value=raw??data.decimal??(data.lat+', '+data.lon);status('coordinateFormats','Decimal: '+data.decimal+' · DMS: '+data.dms);$('openGoogleEarth').href='https://earth.google.com/web/@'+data.lat+','+data.lon+',0a,1500d,35y,0h,0t,0r';$('locationLat').value=data.lat.toFixed(8);$('locationLon').value=data.lon.toFixed(8);status('locationUTM',(data.utm?'UTM WGS84: '+data.utm:'Local fora da cobertura UTM.')+' — confira a posição no projeto.');
  $('useLocation').disabled=$('newLocationPoint').disabled=false;
  const link=$('externalLocation');link.href='https://www.openstreetmap.org/?mlat='+data.lat+'&mlon='+data.lon+'#map=18/'+data.lat+'/'+data.lon;link.hidden=false;
  if(refit)fit();else draw();
 }
 async function search(){
  const q=$('addressQuery').value.trim(),ticket=++request,current=Book.summary();
  $('addressResults').replaceChildren();if(q.length<4){status('addressStatus','Digite ao menos 4 caracteres.');return;}
  status('addressStatus','Pesquisando…');
  try{const data=await api('/api/location-search',{query:q});if(ticket!==request||current!==Book.summary())return;
   results=data.results;status('addressStatus',results.length?'Selecione uma localização aproximada.':'Nenhuma sugestão encontrada. Inclua cidade e estado ou informe coordenadas.');
   $('addressResults').innerHTML=results.map((r,i)=>`<button type="button" class="secondary" data-address="${i}" style="display:block;width:100%;text-align:left;margin:8px 0">${esc(r.label)}<br><small>${esc(r.utm)}</small></button>`).join('');
  }catch(error){if(ticket===request)status('addressStatus',error.message);}
 }
 $('addressQuery').oninput=()=>{request++;clearTimeout(timer);timer=setTimeout(search,1000);};
 $('addressQuery').onkeydown=ev=>{if(ev.key==='Enter'){ev.preventDefault();clearTimeout(timer);search();}};
 host.addEventListener('click',run(async ev=>{const el=ev.target.closest('button');if(!el)return;
  if(el.dataset.address!==undefined){const r=results[Number(el.dataset.address)];if(r)await select(r.lat,r.lon);}
  if(el.dataset.geofocus!==undefined){const f=Book.summary().geography[Number(el.dataset.geofocus)],p=allCoords(f)[0];await select(p[1],p[0]);}
  if(el.dataset.georemove!==undefined){const f=Book.summary().geography[Number(el.dataset.georemove)];Book.removeGeography(f.id);}
 }));
 const invalidate=()=>{request++;selected=null;$('useLocation').disabled=$('newLocationPoint').disabled=true;$('externalLocation').hidden=true;status('coordinateFormats','');status('locationUTM','Clique em Conferir coordenada para validar.');};
 $('convertLocation').onclick=run(()=>{const raw=$('coordinateInput').value.trim();if(raw)return select(null,null,true,raw);if(!$('locationLat').value.trim()||!$('locationLon').value.trim())throw Error('Cole a coordenada completa ou informe latitude e longitude.');return select(Number($('locationLat').value.replace(',','.')),Number($('locationLon').value.replace(',','.')));});
 $('coordinateInput').oninput=invalidate;
 $('coordinateInput').onkeydown=ev=>{if(ev.key==='Enter'){ev.preventDefault();$('convertLocation').click();}};
 for(const id of ['locationLat','locationLon'])$(id).oninput=()=>{$('coordinateInput').value='';invalidate();};
 $('useLocation').onclick=run(()=>Book.applyLocation(selected));$('newLocationPoint').onclick=run(()=>Book.applyLocation(selected,true));
 $('fitGeography').onclick=fit;
 $('geographyToCroqui').onclick=run(async()=>{
  if(!(Book.summary().geography||[]).length&&!points().length)throw Error('Importe um projeto ou cadastre pontos antes de gerar o croqui.');
  const current=Book.summary(),copy=$('geographyPreview').cloneNode(true);copy.setAttribute('xmlns','http://www.w3.org/2000/svg');copy.setAttribute('width','2400');copy.setAttribute('height','1200');copy.removeAttribute('style');
  const url=URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(copy)],{type:'image/svg+xml'}));
  try{const image=new Image();await new Promise((resolve,reject)=>{image.onload=resolve;image.onerror=()=>reject(Error('Falha ao gerar imagem do projeto.'));image.src=url;});
   const canvas=document.createElement('canvas');canvas.width=2400;canvas.height=1200;const ctx=canvas.getContext('2d');ctx.fillStyle='#fff';ctx.fillRect(0,0,2400,1200);ctx.drawImage(image,0,0,2400,1200);
   const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));if(!blob)throw Error('Falha ao criar imagem.');if(current!==Book.summary())throw Error('A obra mudou durante a exportação.');await Book.appendGeoCroqui(new File([blob],'Referencia_Google_Earth.png',{type:'image/png'}));
  }finally{URL.revokeObjectURL(url);}
 });
 $('earthFile').onchange=run(async ev=>{const file=ev.target.files[0],current=Book.summary();try{if(!file)return;if(file.size>10*1024*1024)throw Error('Limite de 10 MB.');status('earthStatus','Importando…');const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(',')[1]);reader.onerror=()=>reject(Error('Não foi possível ler o arquivo.'));reader.readAsDataURL(file);});const result=await api('/api/earth-import',{name:file.name,data});if(current!==Book.summary())throw Error('A obra mudou durante a importação. Importe novamente na obra desejada.');Book.mergeGeography(result.features);fit();status('earthStatus',result.features.length+' elementos lidos. Reimportações idênticas não duplicam elementos. '+result.warnings.join(' '));}catch(error){status('earthStatus',error.message);}finally{ev.target.value='';}});
 const svg=$('geographyPreview');
 const position=ev=>{const r=svg.getBoundingClientRect();return [(ev.clientX-r.left)/r.width,(ev.clientY-r.top)/r.height];};
 svg.addEventListener('wheel',ev=>{ev.preventDefault();if(!view)return;const [u,v]=position(ev),factor=ev.deltaY>0?1.2:1/1.2;const width=Math.max(.00001,Math.min(360,view[2]*factor));view=[view[0]+u*(view[2]-width),view[1]+v*(view[3]-width/2),width,width/2];draw();},{passive:false});
 svg.onpointerdown=ev=>{if(ev.button!==0&&ev.button!==1)return;ev.preventDefault();drag={x:ev.clientX,y:ev.clientY,view:[...view]};svg.setPointerCapture(ev.pointerId);};
 svg.onpointermove=ev=>{if(!drag)return;const r=svg.getBoundingClientRect();view=[drag.view[0]-(ev.clientX-drag.x)/r.width*drag.view[2],drag.view[1]-(ev.clientY-drag.y)/r.height*drag.view[3],...drag.view.slice(2)];draw();};
 svg.onpointerup=ev=>{if(!drag)return;const moved=Math.hypot(ev.clientX-drag.x,ev.clientY-drag.y);drag=null;if(svg.hasPointerCapture(ev.pointerId))svg.releasePointerCapture(ev.pointerId);if(moved<4){const [u,v]=position(ev),p=inverse([view[0]+u*view[2],view[1]+v*view[3]]);run(()=>select(p.lat,p.lon,false))();}};
 svg.onpointercancel=()=>{drag=null;};
 window.Geography={refresh};refresh();
})();
