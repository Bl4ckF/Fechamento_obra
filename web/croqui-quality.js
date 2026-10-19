'use strict';
// O modelo continua em 1200 x 800; os pixels da imagem são independentes dele.
(() => {
 const maxSide=6000,maxPixels=24000000,maxBytes=32000000;
 function sourceSize(width,height,upscale=false){
  if(!(width>0&&height>0))throw Error('A página não possui dimensões válidas.');
  const scale=Math.min(upscale?Infinity:1,maxSide/Math.max(width,height),Math.sqrt(maxPixels/(width*height)));
  return {width:Math.max(1,Math.floor(width*scale)),height:Math.max(1,Math.floor(height*scale)),scale};
 }
 function exportSize(picture){
  const scale=Math.min(5,Math.max(2,picture?Math.max(picture.width/1200,picture.height/800):2));
  return {width:Math.round(1200*scale),height:Math.round(800*scale),scale};
 }
 function pngData(canvas){
  const data=canvas.toDataURL('image/png');
  if(!data.startsWith('data:image/png;base64,'))throw Error('Não foi possível preparar a imagem do croqui.');
  if((data.length-22)*.75>maxBytes)throw Error('O croqui ultrapassa 32 MB em PNG. Recorte a área necessária do projeto antes de importar.');
  return data;
 }
 window.CroquiQuality={sourceSize,exportSize,pngData};
})();
