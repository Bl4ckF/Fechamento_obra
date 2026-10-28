# Atualização 1.6.0 — pontos, tutorial e leitor de fotos

## Publicação e instalação

Coloque o ZIP em ZIPS do publicador, execute PREPARAR_PUBLICACAO.bat,
selecione o pacote e informe 1.6.0. Publique os arquivos gerados em
ATUALIZACOES/v1.6.0/ENVIAR_NO_GITHUB. O pacote precisa da assinatura do
publicador; não contém chave privada. Preserve a pasta dados.

Depois de atualizar, execute INSTALAR_LEITOR_FOTOS.bat na pasta do programa
uma única vez para instalar Pillow e RapidOCR. A instalação baixa dependências
pela internet, no Python usado pelo aplicativo, sem solicitar administrador.
Restrições corporativas e incompatibilidades do Python podem impedir a instalação.
Reinicie o programa após concluir. As fotos são reconhecidas localmente.

## Condutores

Em Fechamento → Pontos e serviços, use Trechos de condutores para informar
pontos inicial e final, movimento, descrição, bitola, comprimento, quantidade
de condutores e acréscimo. A etapa Croqui fica dedicada ao projeto.
A somagem documenta os trechos: os materiais devem continuar lançados nos
serviços, evitando uma soma automática em duplicidade.

## Tutorial do primeiro acesso

A tela inicial, Fechamento e Poda têm guias próprios, com destaque do elemento,
caixas de diálogo, Voltar, Próximo, Concluir e Ver depois. O botão Tutorial
reabre o guia. A preferência é guardada neste navegador; limpar seus dados
ou trocar de navegador faz o guia aparecer novamente.

## Fotos Timestamp

1. Abra Leitor de fotos e selecione até 100 fotos JPG, PNG ou WebP.
2. Clique em Ler fotos selecionadas. O programa procura obra/OS, ponto,
   endereço, coordenadas, data/hora e indicação de antes/depois no texto.
   Também consulta o GPS EXIF, quando existir.
3. Confira os campos com a imagem. Corrija erros e preencha dados ausentes.
   Coordenadas divergentes ou múltiplas precisam de escolha manual.
4. Marque a confirmação e clique em Criar pastas e copiar fotos.
5. Para usar no fechamento, preencha o número da obra atual e selecione
   somente fotos dessa obra. Clique em Adicionar à obra atual. Pontos ausentes
   são criados; fotos são acrescentadas aos pontos com o mesmo número.

As fotos originais são preservadas. Cada lote cria uma pasta em
dados/fotos_organizadas/LOTE_..., contendo OBRA_.../PONTO_.../fotos,
metadados JSON e indice.json. Sufixos nos nomes evitam colisões entre nomes
parecidos. Abrir pasta do lote abre o Explorer no Windows.
Repetir a organização cria um novo lote. Limpar lista remove apenas a lista
de conferência; não apaga imagens, lotes ou fotos já anexadas ao book.

Limites: 18 MB e 40 megapixels por imagem. O OCR pode errar texto pequeno,
borrado, coberto ou com pouco contraste. Não deduz obra e ponto pela paisagem.
O leitor não aplica OCR ao croqui PDF. Fotos e lotes são locais e não são
enviados ao GitHub. Faça cópia da pasta dados para preservar esses arquivos.

## Validação desta versão

Testes automatizados de extração, organização sem sobrescrever originais,
coordenadas conflitantes, caminhos e vínculo com a obra. Reconhecimento real
com imagem Timestamp sintética. A regressão de Poda passou em Chromium;
a validação completa do novo leitor no navegador foi interrompida pela revisão
automática do ambiente por uma possível chamada de telemetria externa. O instalador
BAT e a abertura do Explorer precisam de conferência em um computador Windows.
Books e relatórios continuam sem marca d'água do desenvolvedor.
