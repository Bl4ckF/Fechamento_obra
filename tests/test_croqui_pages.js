const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const web=path.join(__dirname,'../web'),env={window:{},crypto:require('node:crypto').webcrypto};vm.createContext(env);
vm.runInContext(fs.readFileSync(path.join(web,'croqui-pages.js'),'utf8'),env);const pages=env.window.CroquiPages;
assert.deepEqual(Array.from(pages.selection('single','',12,7)),[7]);assert.deepEqual(Array.from(pages.selection('all','',3)),[1,2,3]);assert.deepEqual(Array.from(pages.selection('range','2-5, 3,8,10-11',12)),[2,3,4,5,8,10,11]);
for(const [mode,value,total,current] of [['single','',5,0],['single','',5,6],['single','',5,1.5],['range','5-2',6],['range','1,',6],['range','1.5',6],['range','0',6],['range','2-20',6],['all','',101],['range','1-101',200],['range','',20]])assert.throws(()=>pages.selection(mode,value,total,current));
const legacy={croqui:{ref:'a'.repeat(64)+'.png',caption:'Original'},drawing:{objects:[]}};
const imported=pages.fromBook(legacy);assert.equal(imported.length,1);assert.equal(imported[0].croqui,legacy.croqui);assert.equal(pages.fromBook({...legacy,croqui_pages:[]}).length,0);
const made=pages.page(legacy.croqui,{kind:'pdf',page:3},{texts:[{id:'pdf_0'}],cleanRef:'b'.repeat(64)+'.png',lines:[{id:'pdfline_12'}],pdfRef:'c'.repeat(64)+'.pdf'});assert.equal(made.drawing.background_source.page,3);assert.equal(made.drawing.pdf_lines.length,1);assert.equal(made.drawing.pdf_texts.length,1);assert.notEqual(made.id,imported[0].id);
console.log('OK: seleção de uma página, todas, intervalos/listas, validação e migração de croqui antigo.');
