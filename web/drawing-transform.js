'use strict';
// Transformações em coordenadas do documento, independentes do zoom da tela.
(() => {
 const copy=o=>JSON.parse(JSON.stringify(o)),deg=r=>r*180/Math.PI;
 const angle=a=>((a+180)%360+360)%360-180;
 function frame(o){
  const b=window.Drawing.bounds(o),pivot=(o.type==='symbol'||o.type==='text')?{x:o.x1,y:o.y1}:{x:b.x+b.w/2,y:b.y+b.h/2};
  return {pivot,box:b};
 }
 function apply(original,kind,start,end,snap=false){
  const o=copy(original),{pivot:p}=frame(o),a={x:start.x-p.x,y:start.y-p.y},b={x:end.x-p.x,y:end.y-p.y};
  let delta=deg(Math.atan2(b.y,b.x)-Math.atan2(a.y,a.x)),ratio=Math.hypot(b.x,b.y)/Math.max(1,Math.hypot(a.x,a.y));
  if(kind==='rotate'){
   if(o.type==='symbol'||o.type==='text'){const value=(o.rotation||0)+delta;o.rotation=angle(snap?Math.round(value/15)*15:value);return o;}
   if(snap)delta=Math.round(delta/15)*15;ratio=1;
  }else{
   delta=0;if(snap)ratio=Math.round(ratio*10)/10;
   if(o.type==='symbol'||o.type==='text'){o.size=Math.max(o.type==='symbol'?7:2,Math.min(o.type==='symbol'?700:160,o.size*ratio));if(o.text_width!==undefined)o.text_width*=o.size/original.size;return o;}
   ratio=Math.max(.02,Math.min(100,ratio));
  }
  const r=delta*Math.PI/180,c=Math.cos(r)*ratio,s=Math.sin(r)*ratio;
  window.PDFLines.transform(o,[c,s,-s,c,p.x-c*p.x+s*p.y,p.y-s*p.x-c*p.y]);
  // Evita exportar coordenadas fora da página: reduz para caber e reposiciona.
  let bounds=window.PDFLines.bounds(o),fit=Math.min(1,1200/Math.max(1,bounds.w),800/Math.max(1,bounds.h));
  if(fit<1)window.PDFLines.transform(o,[fit,0,0,fit,p.x*(1-fit),p.y*(1-fit)]);
  bounds=window.PDFLines.bounds(o);window.PDFLines.transform(o,[1,0,0,1,Math.max(0,-bounds.x)+Math.min(0,1200-bounds.x-bounds.w),Math.max(0,-bounds.y)+Math.min(0,800-bounds.y-bounds.h)]);
  return o;
 }
 window.DrawingTransform={frame,apply};
})();
