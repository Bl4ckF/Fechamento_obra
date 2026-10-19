'use strict';
(() => {
 const cache=new WeakMap();
 const normalize=value=>String(value||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase('pt-BR').replace(/\s+/g,' ').trim();
 function entries(doc){
  if(!doc)return [];if(cache.has(doc))return cache.get(doc);
  const changes=new Map((doc.objects||[]).map(o=>[o.id,o])),items=[];
  for(const source of doc.pdf_texts||[]){const o=changes.get(source.id)||source;if(o.text&&!o.deleted)items.push({objectId:o.id,kind:'text',text:o.text,normalized:normalize(o.text)});}
  for(const o of doc.objects||[]){if(o.deleted||o.pdf_text_id)continue;const text=o.type==='text'?o.text:o.label;if(text)items.push({objectId:o.id,kind:o.type,text,normalized:normalize(text)});}
  cache.set(doc,items);return items;
 }
 function find(pages,query,currentId,scope='all'){
  const value=normalize(query);if(!value)return [];const result=[];
  pages.forEach((page,pageIndex)=>{if(scope==='current'&&page.id!==currentId)return;for(const item of entries(page.drawing))if(item.normalized.includes(value))result.push({...item,pageId:page.id,pageIndex,sourcePage:page.drawing?.background_source?.page,sourceName:page.drawing?.background_source?.name||''});});
  return result;
 }
 window.PDFSearch={normalize,find};
})();
