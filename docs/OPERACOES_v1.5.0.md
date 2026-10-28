# Poda e Fechamento — v1.5.0

## Instalar e iniciar

Este ZIP é uma atualização cumulativa para a instalação completa do Fechamento, base v1.3.5. Use o publicador para assinar e validar; anexe o ZIP e sua assinatura na Release v1.5.0. Os computadores devem já ter recebido a transição de segurança v1.3.8.

Após atualizar, execute uma vez `INSTALAR_RECURSOS_PODA.bat` na pasta do programa. Ele instala Pillow e ReportLab no mesmo Python selecionado pelo iniciador, sem administrador. Requer internet e permissão para instalar pacotes Python no perfil do usuário; erros de instalação são exibidos. O Fechamento permanece disponível mesmo sem essas dependências; a Poda informa o que falta.

Abra `INICIAR.bat`: a tela inicial pergunta PODA ou FECHAMENTO. Cada operação tem um link para voltar à seleção, salvando o rascunho antes de sair.

## Poda

Adaptada do arquivo Book_Poda_v12.5.0_completo_Localhost.zip fornecido no projeto:

- Poda e Limpeza de Faixa, com as equipes e o modelo PDF do programa original.
- Fotos ANTES e DEPOIS por arquivo, arrastar/soltar ou colar.
- Rascunho automático, incluindo evidência em preenchimento.
- Geração de PDF, consulta dos registros e edição com preservação da versão anterior.
- Catálogo de materiais e consulta das ordens de serviço do programa original. Consulta da planilha e de endereços precisa de internet; erros de rede não impedem preencher manualmente.
- Referências locais de TD/religador mantidas. O mapa QField não foi reinserido.

Dados ficam em `dados/poda`; por padrão PDFs e fotos ficam em `dados/poda/Books/Ano/Mês`. Pode configurar outra pasta de saída na Poda. Os registros da instalação separada do Book Poda não são importados automaticamente: preserve essa instalação e seu histórico.

O backup JSON do Fechamento continua cobrindo apenas o Fechamento. Para resguardar Poda, com o programa fechado copie `dados/poda` e qualquer pasta externa configurada para saída de PDFs/fotos. As atualizações preservam `dados`.

## Coordenadas

O campo único aceita graus decimais com ponto ou vírgula, DMS, graus/minutos decimais, letras N/S/E/W/O antes ou depois dos valores, UTM com fuso/faixa (21K) ou hemisfério explícito (21 SUL). Mostra decimal, DMS e UTM para conferência. Valores sem fuso ou com formato ambíguo são recusados. A referência é WGS84: não presume o datum de arquivos externos nem aceita automaticamente qualquer projeção EPSG/MGRS.

## Google Earth

O Google Earth Web responde com a restrição `X-Frame-Options: SAMEORIGIN`, bloqueando incorporação no aplicativo localhost. Não há um Earth embutido nesta atualização. O botão da aba abre o serviço oficial em outra janela; exporte KML/KMZ e importe no Fechamento. A prévia local continua sem imagens de satélite.

Rodar um navegador dedicado dentro de uma janela de aplicativo exige uma etapa desktop e validação própria; não foi implementado aqui. Nenhuma restrição do Google foi removida ou contornada.

## Segurança e testes

As duas operações usam o mesmo servidor local e proteção de Host/origem/token. O atualizador antigo da Poda não é carregado: atualize as duas operações pelo sino do Fechamento. Nenhuma nova porta ou servidor para a equipe é necessário.

Books/PDFs não recebem a marca do desenvolvedor; os créditos ficam somente nas telas.

Validação em ambiente de desenvolvimento: testes Python, fluxo real no Chromium de entrada, fotos, rascunho, PDF e edição; validação da instalação incremental. Falta teste nativo no Windows e assinatura com a chave do responsável pela publicação.
