# Operações integradas ao Fechamento

Os módulos são compilados dos projetos irmãos (`../pdfcraft`, `../cadcraft`,
`../photocraft`, somente). A pasta de executáveis `../apps` não é usada.
Os artefatos web ficam em `web/operations/<operação>` dentro da instalação do
Fechamento: não há processo desktop nem servidor separado para cada editor.

A etapa **Edição** reúne CADCraft, PDFCraft e PhotoCraft na própria página.
Não há balão de operações, aba de leitor de fotos ou Google Earth no Fechamento.
As quatro etapas principais permanecem visíveis. **Outras opções** permite
expandir/recolher as abas secundárias e memoriza essa preferência.
**Minimizar editor** recolhe a área de trabalho sem encerrar o editor ou
descartar alterações. **Croqui do book · importar e conferir** reúne os
controles de vinculação do documento ao book, separadamente dos três editores.

PDFCraft recebe o PDF do croqui pelo protocolo de incorporação existente no
seu código-fonte. PDFCraft e CADCraft devolvem salvamentos pelo mesmo
protocolo. PhotoCraft tem suas exportações de navegador adaptadas ao
armazenamento interno. Documentos salvos ficam no banco, vinculados ao rascunho,
e entram no backup JSON do Fechamento. PDFs e imagens salvos podem substituir o
croqui após confirmação. O navegador continua exigindo a seleção das páginas
na importação de PDF. Para reabrir um documento em módulos sem protocolo nativo,
use **Reabrir** e depois **Arquivo → Abrir** dentro da operação.

## Compilação

Ferramentas de desenvolvimento: Rust com `wasm32-unknown-unknown`, Trunk e
wasm-bindgen CLI na versão dos fontes. Não são necessárias no computador que
receber a instalação já compilada.

Execute `tools/compilar_operacoes.ps1` para empacotar os módulos dos fontes.
O script usa Trunk para projetos com página de entrada Trunk e `cargo xtask web`
para os projetos que têm empacotador próprio. Também copia os avisos de licença.
Caches de compilação ficam no diretório temporário, com caminho sem acentos
para compatibilidade com MinGW. As fontes originais não são movidas.

O catálogo só marca um editor como disponível quando existem a página e o
módulo WebAssembly empacotados. Um botão não comprova que a compilação ou a
validação de funcionamento foi concluída.
