'use strict';
// Coordenadas dos textos do PDF no documento de croqui (1200 x 800).
(() => {
 const families=['Arial','Times New Roman','Courier New'];
 function mapText(content,viewport,pdfjs,canvasWidth,canvasHeight){
  const scale=Math.min(1200/canvasWidth,800/canvasHeight),ox=(1200-canvasWidth*scale)/2,oy=(800-canvasHeight*scale)/2,texts=[];
  for(const item of content.items){
   if(!item.str?.trim())continue;
   const style=content.styles[item.fontName]||{};
   // Escrita vertical requer composição específica; continua visível no fundo.
   if(style.vertical||item.str.length>2000)continue;
   const t=pdfjs.Util.transform(viewport.transform,item.transform),size=Math.hypot(t[2],t[3])*scale;
   if(size<2||size>160)continue;
   const angle=Math.atan2(t[1],t[0]),width=Math.abs(item.width*viewport.scale*scale),ascent=(style.ascent??.85)*size,descent=Math.abs(style.descent??-.22)*size;
   const x=t[4]*scale+ox,y=t[5]*scale+oy,c=Math.cos(angle),s=Math.sin(angle);
   const corners=[[0,-ascent],[width,-ascent],[0,descent],[width,descent]].map(([u,v])=>({x:x+u*c-v*s,y:y+u*s+v*c}));
   const minX=Math.max(0,Math.min(...corners.map(p=>p.x))-1.5),minY=Math.max(0,Math.min(...corners.map(p=>p.y))-1.5),maxX=Math.min(1200,Math.max(...corners.map(p=>p.x))+1.5),maxY=Math.min(800,Math.max(...corners.map(p=>p.y))+1.5);
   if(x<0||x>1200||y<0||y>800||maxX<=minX||maxY<=minY)continue;
   const family=style.fontFamily||'',font=/mono/i.test(family)?families[2]:/(^|[^-])serif/i.test(family)?families[1]:families[0];
   texts.push({id:'pdf_'+texts.length,text:item.str,x1:x,y1:y,size,rotation:angle*180/Math.PI,text_width:width,font,color:'#111111',bold:false,italic:false,box:{x:minX,y:minY,w:maxX-minX,h:maxY-minY}});
  }
  return texts;
 }
 function textFilter(pdfjs){
  const skip=new Set(['showText','showSpacedText','nextLineShowText','nextLineSetSpacingShowText'].map(key=>pdfjs.OPS[key]));
  return (index,operators)=>{if(!operators)throw Error('Atualize os arquivos PDF.js do programa.');return !skip.has(operators.fnArray[index]);};
 }
 function editable(source){return {...source,type:'text',pdf_text_id:source.id,width:1,dash:'solid',arrow:'none'};}
 function textBounds(object){
  const angle=(object.rotation||0)*Math.PI/180,c=Math.cos(angle),s=Math.sin(angle),width=object.text_width??Math.max(object.size*.4,object.text.length*object.size*.65);
  const height=object.size*1.25,lines=String(object.text).split('\n'),w=Math.max(...lines.map(line=>line.length))*object.size*.65;
  const end=lines.length>1?Math.max(width,w):width;
  const pts=[[0,-object.size],[end,-object.size],[0,height*(lines.length-1)+object.size*.25],[end,height*(lines.length-1)+object.size*.25]].map(([u,v])=>({x:object.x1+u*c-v*s,y:object.y1+u*s+v*c}));
  const x=Math.min(...pts.map(p=>p.x)),y=Math.min(...pts.map(p=>p.y));return {x,y,w:Math.max(...pts.map(p=>p.x))-x,h:Math.max(...pts.map(p=>p.y))-y};
 }
 window.PDFText={mapText,textFilter,editable,textBounds,families};
})();
