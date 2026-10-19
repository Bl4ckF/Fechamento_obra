'use strict';
self.window=self;
importScripts('/pdf-text.js','/pdf-lines.js','/network-symbols.js','/drawing.js');
self.onmessage=async({data})=>{
 const {id,doc,size,catalog,original,clean}=data;let canvas;
 try{
  NetworkSymbols.setCatalog({symbols:catalog});canvas=new OffscreenCanvas(size.width,size.height);const ctx=canvas.getContext('2d');ctx.scale(size.width/1200,size.height/800);ctx.imageSmoothingQuality='high';Drawing.render(ctx,doc,'',false,{original,clean});
  const blob=await canvas.convertToBlob({type:'image/png'});self.postMessage({id,blob});
 }catch(error){self.postMessage({id,error:error.message});}finally{original?.close();clean?.close();if(canvas)canvas.width=canvas.height=1;}
};
