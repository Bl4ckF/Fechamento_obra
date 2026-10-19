'use strict';
(() => {
 let catalog=[],custom=[];const byId=new Map();
 const statusLabel={existente:'Existente',instalar:'Instalar',retirar:'Desativar'};
 function setCatalog(data){catalog=data?.symbols||[];byId.clear();for(const item of catalog)byId.set(item.id,item);}
 function get(id){return custom.find(s=>s.id===id)||byId.get(id);}
 function setCustom(items){custom=items||[];}
 function upsert(item){custom=custom.filter(s=>s.id!==item.id).concat([item]);}
 function drafts(){return custom;}
 function usable(s){return !!s?.name?.trim()&&s.ops?.length>0;}
 function all(){return catalog.concat(custom.filter(usable));}
 function make(id,x,y){const source=get(id);if(!source)throw Error('Símbolo não encontrado. Recarregue o programa.');return {...(id.startsWith('user_')?{symbol_definition:JSON.parse(JSON.stringify(source))}:{}),id:'sym_'+crypto.randomUUID().replaceAll('-',''),type:'symbol',symbol_id:id,x1:x,y1:y,size:70,rotation:0,color:source.color||'#243c4c',width:2.5,dash:'solid',arrow:'none',status:'instalar',label:source.tag||source.name,opaque:false};}
 function bodyBounds(source){
  if(!source?.id?.startsWith('user_'))return {x:-50,y:-50,w:100,h:100};
  let left=-50,top=-50,right=50,bottom=50;
  function point(x,y){left=Math.min(left,x);top=Math.min(top,y);right=Math.max(right,x);bottom=Math.max(bottom,y);}
  for(const [kind,...v] of source.ops){
   if(kind==='line'){point(v[0],v[1]);point(v[2],v[3]);}
   if(kind==='rect'){point(v[0],v[1]);point(v[0]+v[2],v[1]+v[3]);}
   if(kind==='circle'||kind==='arc'){point(v[0]-v[2],v[1]-v[2]);point(v[0]+v[2],v[1]+v[2]);}
   if(kind==='poly')v[0].forEach(p=>point(...p));
   if(kind==='text'){point(v[0]-45,v[1]-v[3]);point(v[0]+45,v[1]+v[3]*.25);}
  }
  return {x:left-2,y:top-2,w:right-left+4,h:bottom-top+4};
 }
 function draw(c,o){
  const source=o.symbol_definition||get(o.symbol_id),body=bodyBounds(source);if(!source)throw Error('Símbolo ausente da biblioteca: '+o.symbol_id);
  c.save();c.translate(o.x1,o.y1);c.rotate((o.rotation||0)*Math.PI/180);c.scale(o.size/100,o.size/100);
  c.strokeStyle=o.color;c.fillStyle=o.color;c.lineWidth=o.width||2.5;c.lineCap='round';c.lineJoin='round';c.setLineDash(source.line&&o.status==='instalar'?[9,6]:[]);
  if(o.opaque){c.fillStyle='#fff';c.fillRect(body.x,body.y,body.w,body.h);c.fillStyle=o.color;}
  for(const op of source.ops){
   const [kind,...v]=op;c.beginPath();
   if(kind==='line'){c.moveTo(v[0],v[1]);c.lineTo(v[2],v[3]);c.stroke();}
   if(kind==='arc'){c.arc(v[0],v[1],v[2],v[3]*Math.PI/180,v[4]*Math.PI/180);c.stroke();}
   if(kind==='circle'||kind==='rect'||kind==='poly'){
    let fill;if(kind==='circle'){c.arc(v[0],v[1],v[2],0,Math.PI*2);fill=v[3];}else if(kind==='rect'){c.rect(v[0],v[1],v[2],v[3]);fill=v[4];}else{v[0].forEach((p,i)=>i?c.lineTo(p[0],p[1]):c.moveTo(p[0],p[1]));c.closePath();fill=v[1];}
    if(fill===true||(fill==='projetado'&&o.status==='instalar'))c.fill();c.stroke();
   }
   if(kind==='text'){c.save();c.setLineDash([]);c.textAlign='center';c.font=(v[3]||18)+'px Arial';c.fillText(v[2],v[0],v[1],source.id.startsWith('user_')?90:1000);c.restore();}
  }
  c.setLineDash([]);
  if(o.status==='retirar'){c.lineWidth=2.5;c.beginPath();c.moveTo(-43,-43);c.lineTo(43,43);c.moveTo(-43,43);c.lineTo(43,-43);c.stroke();}
  if(o.label){c.font='14px Arial';c.textAlign='center';const text=String(o.label).slice(0,96),parts=text.match(/.{1,24}/g)||[];parts.forEach((line,i)=>c.fillText(line.trim(),0,body.y+body.h+16+i*16,160));}
  c.restore();
 }
 function bounds(o){const body=bodyBounds(o.symbol_definition||get(o.symbol_id)),left=o.label?Math.min(-80,body.x):body.x,right=o.label?Math.max(80,body.x+body.w):body.x+body.w,bottom=body.y+body.h+(o.label?24+Math.min(3,Math.floor((o.label.length-1)/24))*16:0),scale=o.size/100,angle=(o.rotation||0)*Math.PI/180,c=Math.cos(angle),s=Math.sin(angle);const pts=[[left,body.y],[right,body.y],[left,bottom],[right,bottom]].map(([x,y])=>({x:o.x1+scale*(x*c-y*s),y:o.y1+scale*(x*s+y*c)}));const x=Math.min(...pts.map(p=>p.x)),y=Math.min(...pts.map(p=>p.y));return {x,y,w:Math.max(...pts.map(p=>p.x))-x,h:Math.max(...pts.map(p=>p.y))-y};}
 window.NetworkSymbols={setCatalog,setCustom,upsert,drafts,usable,get,all,make,draw,bounds,bodyBounds,statusLabel};
})();
