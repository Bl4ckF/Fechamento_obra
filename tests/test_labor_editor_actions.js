/* Reset e remoção não podem apagar outro lançamento nem ressuscitar rascunhos. */
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const elements=new Map(),cache=new Map(),calls=[];
function element(id){if(!elements.has(id))elements.set(id,{value:'',textContent:'',innerHTML:'',hidden:false,classList:{toggle(){}},querySelector(){return null;}});return elements.get(id);}
const book={points:[{id:'p1',photos:[{ref:'foto.png'}]},{id:'p2',photos:[]}],croqui_pages:[{croqui:{ref:'croqui.png'}}],point_drafts:{}};
const context={document:{getElementById:element},window:{addEventListener(){},Book:{summary:()=>book,value:()=>book,activeId:()=> 'p1',autosave(){},invalidateForms(){},renderPointList(){}},Training:{flush:async()=>calls.push('saved')}},
 crypto:require('node:crypto').webcrypto,localStorage:{setItem:(k,v)=>cache.set(k,v)},setTimeout:()=>1,clearTimeout(){},console};
vm.createContext(context);vm.runInContext(fs.readFileSync(path.join(__dirname,'../web/app.js'),'utf8'),context);
vm.runInContext(`renderLabor=renderServices=renderEditor=()=>{};recalculate=async()=>{};
 S.labor={labor:{id:'labor',operation:'INSTALAR'}};
 api=async(path,payload)=>{if(path!=='/api/base'||!payload.original)throw Error('Unexpected request');return {editor:{labor_id:'labor',base_id:'base',base_mode:'instalado',variant:'Base original',materials:[{material_id:'m1',coefficient:'2'}]}};};`,context);
const run=code=>vm.runInContext(code,context),read=code=>JSON.parse(JSON.stringify(run(code)));
const service=(id,point='p1')=>({entry_id:id,point_id:point,labor_id:'labor',quantity:'1',materials:[{material_id:'m1',coefficient:'2'}],note:'Original',reviewed:true});
const set=value=>{context.fixture=value;run('S.services=cp(fixture);');};
(async()=>{
 element('responsible').value='Responsável teste';element('workOrder').value='OBRA 133';
 set([service('a'),service('b')]);run("S.editor=cp(S.services[1]);S.editing=1;S.selected='labor';rememberEditorStart();S.editor.quantity='9';S.editor.note='Alterado';S.editor.materials[0].coefficient='99';");
 await run('clearEditorChanges()');assert.deepEqual(read('S.editor'),service('b'));assert.deepEqual(read('S.services[0]'),service('a'));assert.equal(run('S.editorTouched'),false);
 assert.equal(element('responsible').value,'Responsável teste');assert.equal(book.points[0].photos[0].ref,'foto.png');assert.equal(book.croqui_pages[0].croqui.ref,'croqui.png');
 const saved=JSON.parse([...cache.values()][0]);assert.equal(saved.editor.note,'Original');assert.equal(saved.editor_baseline.editor.note,'Original');
 // Uma seleção nova restaura o que foi carregado, inclusive depois de recuperar o rascunho.
 run("S.editing=-1;S.editor={...cp(S.services[0]),entry_id:'new',quantity:'3'};rememberEditorStart();S.editor.materials=[];S.editor.quantity='8';persist();");
 const draft=JSON.parse([...cache.values()][0]);context.draft=draft;run('S.editor=draft.editor;S.editorBaseline=draft.editor_baseline;');
 await run('clearEditorChanges()');assert.equal(run('S.editor.quantity'),'3');assert.equal(run('S.editor.materials.length'),1);
 // Uma composição antiga (1.3.2) não tem snapshot; recuperar a base evita reaplicar os ajustes que se está limpando.
 run("S.editor={...S.editor,base_id:'base',base_mode:'instalado'};S.editorBaseline=null;");await run('clearEditorChanges()');assert.equal(run('S.editor.variant'),'Base original');
 // Duas ocorrências da mesma mão de obra: remover apenas a selecionada e limpar seus rascunhos inativos.
 set([service('a'),service('b'),service('c','p2')]);run("S.editor=cp(S.services[1]);S.editing=1;S.selected='labor';");
 book.point_drafts={p1:{editor:service('b'),editing:1},p2:{editor:service('c','p2'),editing:2}};
 await run('removeSelectedLabor()');assert.deepEqual(read('S.services.map(s=>s.entry_id)'),['a','c']);assert.equal(run('S.editor'),null);assert.equal(book.point_drafts.p1,undefined);assert.equal(book.point_drafts.p2.editing,1);
 assert.equal(JSON.parse([...cache.values()][0]).services.length,2);
 // Remover outro lançamento reindexa o editor aberto sem descartar as alterações dele.
 run("S.editor=cp(S.services[1]);S.editor.note='Em edição';S.editing=1;S.selected='labor';rememberEditorStart();");await run('removeService(0)');
 assert.equal(run('S.editing'),0);assert.equal(run('S.editor.note'),'Em edição');assert.equal(run('S.services[0].entry_id'),'c');assert.equal(book.point_drafts.p2.editing,0);
 // Uma seleção ainda não adicionada pode ser descartada sem excluir o serviço já aplicado.
 run("S.editor={...cp(S.services[0]),entry_id:'not-added'};S.editing=-1;S.selected='labor';");await run('removeSelectedLabor()');assert.equal(run('S.services.length'),1);assert.equal(run('S.editor'),null);
 // Se o editor mudar enquanto o salvamento está pendente, a limpeza não atinge o editor novo.
 run("S.editor=cp(S.services[0]);S.editing=0;S.selected='labor';");context.window.Training.flush=async()=>run("S.editor={...S.editor,entry_id:'another',note:'Preservar'};");
 await run('clearEditorChanges()');assert.equal(run('S.editor.note'),'Preservar');
 // Uma remoção que aguarda o autosalvamento acompanha a identidade, mesmo após mudança do índice.
 set([service('a'),service('b'),service('c')]);run('S.editor=null;S.editing=-1;');let first=true;
 context.window.Training.flush=async()=>{if(first){first=false;run('S.services.shift();');}};
 await run('removeService(1)');assert.deepEqual(read('S.services.map(s=>s.entry_id)'),['c']);
 console.log('OK: limpar e remover mão de obra, duplicados, rascunhos por ponto, autosalvamento e mudanças concorrentes.');
})().catch(error=>{console.error(error);process.exitCode=1;});
