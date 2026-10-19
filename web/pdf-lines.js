'use strict';
// Geometria do PDF.js local (v5): caminhos pintados por constructPath.
(() => {
 const identity=()=>[1,0,0,1,0,0];
 const multiply=(a,b)=>[a[0]*b[0]+a[2]*b[1],a[1]*b[0]+a[3]*b[1],a[0]*b[2]+a[2]*b[3],a[1]*b[2]+a[3]*b[3],a[0]*b[4]+a[2]*b[5]+a[4],a[1]*b[4]+a[3]*b[5]+a[5]];
 const point=(m,x,y)=>[m[0]*x+m[2]*y+m[4],m[1]*x+m[3]*y+m[5]];
 const commands=o=>o.type==='line'?[['M',o.x1,o.y1],['L',o.x2,o.y2]]:o.commands;
 function bounds(o){const points=commands(o).flatMap(c=>{const a=[];for(let i=1;i<c.length;i+=2)a.push([c[i],c[i+1]]);return a;});const xs=points.map(p=>p[0]),ys=points.map(p=>p[1]),x=Math.min(...xs),y=Math.min(...ys);return {x,y,w:Math.max(...xs)-x,h:Math.max(...ys)-y};}
 function transform(o,m){
  if(o.type==='line'){[o.x1,o.y1]=point(m,o.x1,o.y1);[o.x2,o.y2]=point(m,o.x2,o.y2);}
  else o.commands=o.commands.map(c=>{const result=[c[0]];for(let i=1;i<c.length;i+=2)result.push(...point(m,c[i],c[i+1]));return result;});return o;
 }
 function pathData(o){return commands(o).map(c=>c.join(' ')).join(' ');}
 function trace(ctx,o){for(const [op,...v] of commands(o)){if(op==='M')ctx.moveTo(...v);else if(op==='L')ctx.lineTo(...v);else if(op==='C')ctx.bezierCurveTo(...v);else if(op==='Q')ctx.quadraticCurveTo(...v);else if(op==='Z')ctx.closePath();}}
 function decode(arr,m){
  const result=[];if(!Array.isArray(arr)&&!ArrayBuffer.isView(arr))return null;
  for(let i=0;i<arr.length;){const kind=arr[i++],size={0:2,1:2,2:6,3:4,4:0}[kind];if(size===undefined||i+size>arr.length)return null;const c=[['M','L','C','Q','Z'][kind]];for(let j=0;j<size;j+=2)c.push(...point(m,arr[i+j],arr[i+j+1]));i+=size;result.push(c);}
  return result;
 }
 function extract(operators,viewport,pdfjs,canvasWidth,canvasHeight){
  const O=pdfjs.OPS,ratio=Math.min(1200/canvasWidth,800/canvasHeight),fit=[ratio,0,0,ratio,(1200-canvasWidth*ratio)/2,(800-canvasHeight*ratio)/2];
  const base=multiply(fit,viewport.transform),stack=[],lines=[];
  let state={matrix:identity(),color:'#000000',width:1,dash:[],dashOffset:0,cap:0,join:0,clip:null,unsafe:false},lastPath=null,pendingClip=false,totalVertices=0;
  const save=()=>stack.push(JSON.parse(JSON.stringify(state))),restore=()=>{state=stack.pop()||state;};
  function clipPath(path){
   if(!path?.length){state.unsafe=true;return;}
   const box=bounds({type:'path',commands:path}),points=path.filter(c=>c[0]!=='Z');
   const rectangle=points.length>=4&&points.length<=5&&points.every((c,i)=>i===0?c[0]==='M':c[0]==='L')&&points.every(c=>(Math.abs(c[1]-box.x)<.001||Math.abs(c[1]-box.x-box.w)<.001)&&(Math.abs(c[2]-box.y)<.001||Math.abs(c[2]-box.y-box.h)<.001));
   if(!rectangle){state.unsafe=true;return;}const previous=state.clip;
   state.clip=previous?{x:Math.max(previous.x,box.x),y:Math.max(previous.y,box.y),right:Math.min(previous.right,box.x+box.w),bottom:Math.min(previous.bottom,box.y+box.h)}:{...box,right:box.x+box.w,bottom:box.y+box.h};
  }
  for(let i=0;i<operators.fnArray.length;i++){
   const op=operators.fnArray[i],args=operators.argsArray[i]||[];
   if(op===O.save){save();continue;}if(op===O.restore){restore();continue;}
   if(op===O.transform){state.matrix=multiply(state.matrix,args);continue;}
   if(op===O.paintFormXObjectBegin){save();if(args[0])state.matrix=multiply(state.matrix,args[0]);if(args[1]){const [x,y,r,b]=args[1],m=multiply(base,state.matrix);clipPath([['M',...point(m,x,y)],['L',...point(m,r,y)],['L',...point(m,r,b)],['L',...point(m,x,b)],['Z']]);}continue;}
   if(op===O.paintFormXObjectEnd){restore();continue;}
   if(op===O.beginGroup){save();state.unsafe=true;continue;}if(op===O.endGroup){restore();continue;}
   if(op===O.setStrokeRGBColor){state.color=args[0];continue;}
   if(op===O.setStrokeColorN||op===O.setStrokeTransparent){state.color=null;continue;}
   if(op===O.setLineWidth){state.width=args[0];continue;}if(op===O.setDash){state.dash=Array.from(args[0]);state.dashOffset=args[1]||0;continue;}
   if(op===O.setLineCap){state.cap=args[0];continue;}if(op===O.setLineJoin){state.join=args[0];continue;}
   if(op===O.setGState){for(const [key,value] of args[0]||[]){if(key==='LW')state.width=value;else if(key==='LC')state.cap=value;else if(key==='LJ')state.join=value;else if(key==='D'){state.dash=Array.from(value[0]);state.dashOffset=value[1]||0;}else if((key==='CA'&&value!==1)||(key==='BM'&&value!=='source-over')||(key==='SMask'&&value))state.unsafe=true;}continue;}
   if(op===O.clip||op===O.eoClip){pendingClip=true;continue;}
   if(op!==O.constructPath)continue;
   const matrix=multiply(base,state.matrix),chunks=args[1]||[],path=chunks.map(c=>decode(c,matrix));
   if(path.some(c=>!c)){lastPath=null;continue;}lastPath=path.flat();
   if(pendingClip){clipPath(lastPath);pendingClip=false;continue;}
   if(![O.stroke,O.closeStroke].includes(args[0])||state.unsafe||!/^#[0-9a-f]{6}$/i.test(state.color||'')||!lastPath.length)continue;
   if(args[0]===O.closeStroke)lastPath.push(['Z']);
   const sx=Math.hypot(matrix[0],matrix[1]),sy=Math.hypot(matrix[2],matrix[3]);
   // Transformações não uniformes mudam a espessura ao longo do traço.
   if(Math.abs(sx-sy)>Math.max(sx,sy)*.01||Math.abs(matrix[0]*matrix[2]+matrix[1]*matrix[3])>sx*sy*.001||!Number.isFinite(state.width*sx)||state.width*sx>30)continue;
   const value={id:'pdfline_'+i,type:'path',commands:lastPath,color:state.color,width:Math.max(.1,Math.min(30,state.width*sx)),dash:state.dash.length?'dashed':'solid',arrow:'none',line_cap:['butt','round','square'][state.cap]||'butt',line_join:['miter','round','bevel'][state.join]||'miter',label:'',operator_index:i};
   if(state.dash.length){value.dash_array=state.dash.map(n=>n*sx);value.dash_offset=state.dashOffset*sx;}
   if(value.dash_array&&(value.dash_array.length>32||value.dash_array.some(v=>!Number.isFinite(v)||v<0||v>1000)||!value.dash_array.some(v=>v>0)||Math.abs(value.dash_offset)>1000))continue;
   const b=bounds(value);if(!Number.isFinite(b.x+b.y+b.w+b.h)||b.w+b.h<.2||lastPath.length>2000)continue;
   if(b.x<0||b.y<0||b.x+b.w>1200||b.y+b.h>800)continue;
   if(state.clip&&(b.x<state.clip.x-.01||b.y<state.clip.y-.01||b.x+b.w>state.clip.right+.01||b.y+b.h>state.clip.bottom+.01))continue;
   if(lastPath.length===2&&lastPath[0][0]==='M'&&lastPath[1][0]==='L'){value.type='line';[value.x1,value.y1]=lastPath[0].slice(1);[value.x2,value.y2]=lastPath[1].slice(1);delete value.commands;}
   const vertices=lastPath.reduce((sum,c)=>sum+(c.length-1)/2,0);if(totalVertices+vertices>100000)continue;totalVertices+=vertices;lines.push(value);if(lines.length>=5000)break;
  }
  return lines;
 }
 function editable(source){const value=JSON.parse(JSON.stringify(source));value.pdf_line_id=source.id;delete value.operator_index;return value;}
 window.PDFLines={extract,editable,bounds,transform,pathData,trace,commands};
})();
