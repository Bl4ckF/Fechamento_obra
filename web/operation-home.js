'use strict';
document.getElementById('operationHome').addEventListener('click',async event=>{
 event.preventDefault();
 try{
  await window.Book.flushCroquis();
  await window.Training?.flush();
  persist();
  await api('/api/draft',{...meta(),services:S.services,selected:S.selected,editor:S.editor,editing:S.editing,editor_touched:S.editorTouched,editor_baseline:S.editorBaseline});
  location.href='/';
 }catch(error){toast(error.message||'Não foi possível salvar antes de sair.',true);}
});
