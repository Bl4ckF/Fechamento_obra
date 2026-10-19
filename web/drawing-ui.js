'use strict';
window.DrawingUI=()=>`
 <div class="section-heading plain"><div><h3>Editar o croqui</h3><p class="muted">Textos, símbolos e linhas podem ser selecionados diretamente na página.</p></div></div>
 <div class="pdf-edit-toolbar">
  <label>Pesquisar no PDF<input id="dPdfSearch" type="search" placeholder="Nome, código, coordenada…"></label><label>Buscar em<select id="dSearchScope"><option value="all">Todas as páginas importadas</option><option value="current">Página atual</option></select></label><button id="dFindPrevious" class="secondary">Anterior</button><button id="dFind" class="secondary">Próximo resultado</button>
  <label>Zoom<select id="dZoom"><option value="0.25">25%</option><option value="0.5">50%</option><option value="1">Ajustar à largura</option><option value="1.5">150%</option><option value="2">200%</option><option value="3">300%</option><option value="4">400%</option><option value="6">600%</option><option value="8">800%</option><option id="dZoomCustom" hidden></option></select></label>
  <button id="dUndo" class="secondary">Desfazer</button><button id="dRedo" class="secondary">Refazer</button><button id="dClear" class="secondary">Limpar alterações do PDF</button><button id="dCancelInsert" class="secondary" hidden>Cancelar inserção</button>
 </div>
 <div id="pdfSearchPanel" class="pdf-search-panel" hidden><p id="pdfSearchCount" role="status" aria-live="polite"></p><div id="pdfSearchResults" aria-label="Resultados da pesquisa"></div><button id="pdfSearchMore" class="secondary" hidden>Mostrar mais resultados</button><small>Busca nos textos selecionáveis e nas legendas editadas das páginas importadas. Imagens escaneadas precisam de OCR externo.</small></div>
 <p id="symbolHint" class="muted" role="status"></p>
 <div class="croqui-editor-layout">
  <aside class="croqui-sidebar" aria-label="Simbologias, linhas e propriedades">
   <div class="sidebar-heading"><strong>Simbologias da rede</strong><span id="symbolCount"></span></div>
   <button id="dSymbolEditor" class="secondary new-line-button">Criar / editar simbologia</button><button id="dNewLine" class="secondary new-line-button">+ Nova linha</button>
   <section id="symbolControls" class="object-properties" hidden><h4 id="symbolSelected"></h4>
    <label>Nome / legenda do símbolo<input id="sLabel" maxlength="96" placeholder="Digite o nome que aparecerá no croqui"></label>
    <div class="property-grid"><label>Escala (%)<input id="sScale" type="number" min="10" max="1000" step="5" value="100"></label><label>Rotação (°)<input id="sRotation" type="number" min="-360" max="360" value="0"></label></div>
    <label>Trocar símbolo<select id="sType"></select></label><label>Situação<select id="sStatus"><option value="existente">Existente</option><option value="instalar">Instalar / projetado</option><option value="retirar">Desativar</option></select></label>
    <div class="property-grid"><label>Cor<input id="sColor" type="color" value="#243c4c"></label><label>X<input id="sX" type="number" min="0" max="1200" value="0"></label><label>Y<input id="sY" type="number" min="0" max="800" value="0"></label></div>
    <label class="check-label"><input id="sOpaque" type="checkbox">Cobrir o símbolo original com fundo branco</label>
    <div class="property-actions"><button id="sEditDrawing" class="secondary">Editar desenho do símbolo</button><button id="sDuplicate" class="secondary">Duplicar</button><button id="sDelete" class="secondary">Excluir</button></div>
    <small>A cobertura branca também oculta as linhas na área coberta.</small>
   </section>
   <section id="lineControls" class="object-properties" hidden><h4 id="lineSelected"></h4>
    <label>Nome / legenda<input id="lLabel" maxlength="96" placeholder="Opcional"></label>
    <div class="property-grid"><label>Cor<input id="lColor" type="color" value="#183e53"></label><label>Espessura<input id="lWidth" type="number" min="0.1" max="30" step="0.1" value="2"></label></div>
    <label>Estilo<select id="lDash"><option value="solid">Contínua</option><option value="dashed">Tracejada</option><option value="dotted">Pontilhada</option></select></label>
    <label>Setas<select id="lArrow"><option value="none">Sem seta</option><option value="end">No final</option><option value="both">Nas duas pontas</option></select></label>
    <div id="lineEndpoints" class="property-grid"><label>X inicial<input id="lX1" type="number" min="0" max="1200"></label><label>Y inicial<input id="lY1" type="number" min="0" max="800"></label><label>X final<input id="lX2" type="number" min="0" max="1200"></label><label>Y final<input id="lY2" type="number" min="0" max="800"></label></div>
    <div id="pathPosition" class="property-grid"><label>Posição X<input id="lX" type="number" min="0" max="1200"></label><label>Posição Y<input id="lY" type="number" min="0" max="800"></label></div>
    <div class="property-actions"><button id="lDuplicate" class="secondary">Duplicar</button><button id="lDelete" class="secondary">Excluir</button><button id="lRestore" class="secondary">Restaurar linha original</button></div>
    <small>Arraste o traço para mover. Em linhas retas, arraste as pontas para alterar o comprimento e a direção.</small>
   </section>
   <section id="textControls" class="object-properties" hidden><h4 id="pdfSelectionLabel"></h4><small>Selecione o texto e arraste o botão ↔ acima dele. Para precisão, altere X e Y abaixo.</small>
    <label>Fonte<select id="dFont"><option>Arial</option><option>Times New Roman</option><option>Courier New</option></select></label>
    <div class="property-grid"><label>Tamanho<input id="dSize" type="number" min="2" max="160" step="0.1" value="22"></label><label>Cor<input id="dColor" type="color" value="#111111"></label><label>X<input id="dX" type="number" min="0" max="1200" value="0"></label><label>Y<input id="dY" type="number" min="0" max="800" value="0"></label><label>Rotação<input id="dRotation" type="number" min="-360" max="360" value="0"></label></div>
    <label class="check-label"><input id="dBold" type="checkbox">Negrito</label><label class="check-label"><input id="dItalic" type="checkbox">Itálico</label>
    <div class="property-actions"><button id="dDelete" class="secondary">Excluir texto</button><button id="dRestoreText" class="secondary">Restaurar texto original</button></div>
   </section>
   <div class="symbol-filters"><input id="symbolSearch" type="search" placeholder="Buscar símbolo…" aria-label="Buscar símbolo"><select id="symbolGroup" aria-label="Categoria"><option value="">Todas as categorias</option></select></div>
   <div id="symbolPalette" class="symbol-palette"></div><small class="symbol-library-note">Símbolos esquemáticos. Confira as convenções da legenda do projeto.</small>
  </aside>
  <div class="croqui-workspace">
   <p class="muted">Roda: zoom. Botão do meio: navegar. Selecione um item: arraste os cantos para mudar a escala ou ↻ para girar. Esc ou clique vazio: desmarcar.</p><p id="dPdfCount" class="muted"></p><p id="lineCount" class="muted"></p><div id="pdfNoText" class="notice"></div>
   <div id="pdfEditorViewport" class="pdf-editor-viewport"><div id="pdfStageSpace"><div id="pdfEditorStage">
    <canvas id="drawingCanvas" width="1200" height="800" aria-label="Página do PDF"></canvas>
    <svg id="lineLayer" viewBox="0 0 1200 800" aria-label="Linhas editáveis"></svg>
    <div id="symbolLayer" aria-label="Símbolos editáveis da rede"></div><div id="pdfTextLayer" aria-label="Textos selecionáveis da página"></div>
    <button id="textMoveHandle" title="Arrastar texto; use as setas para ajustar" aria-label="Mover texto selecionado" hidden>↔</button><div id="transformHandles" aria-label="Rotação e escala"><div id="transformOutline"></div><button id="tRotate" class="transform-handle rotate-handle" title="Arraste para girar · Shift: passos de 15°" aria-label="Girar seleção" hidden>↻</button><button id="tScaleNW" class="transform-handle" aria-label="Redimensionar seleção pelo canto superior esquerdo" hidden></button><button id="tScaleNE" class="transform-handle" aria-label="Redimensionar seleção pelo canto superior direito" hidden></button><button id="tScaleSW" class="transform-handle" aria-label="Redimensionar seleção pelo canto inferior esquerdo" hidden></button><button id="tScaleSE" class="transform-handle" aria-label="Redimensionar seleção pelo canto inferior direito" hidden></button></div><div id="lineHandles"><button id="lHandleStart" class="line-endpoint" aria-label="Mover início da linha" hidden></button><button id="lHandleEnd" class="line-endpoint" aria-label="Mover fim da linha" hidden></button></div>
   </div></div></div>
   <p id="drawingStatus" class="drawing-status" role="status">Pronto para importar o PDF.</p><p id="drawingBackground" class="muted"></p>
   <p class="muted">Alterações salvas automaticamente no croqui e no book. Limpar alterações restaura a página importada. O arquivo PDF original permanece intacto.</p>
  </div>
 </div>`;
