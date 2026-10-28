# Atualização 1.6.2 — recursos e leitor de fotos

## Verificação e instalação pela interface

Na tela inicial, no Fechamento ou na Poda, clique em Recursos do programa.
A verificação identifica o Python que executa o programa, os arquivos do editor
PDF, o processamento de imagens, a geração de PDF de Poda/LF e o motor OCR.
A tela mostra o que está pronto e o que precisa de atenção.

Clique em Instalar recursos no item desejado. O processo usa o mesmo Python
do programa para Poda/LF e mantém o ambiente separado do OCR da versão 1.6.1.
Os downloads precisam de internet e usam instalação para o usuário. Mantenha
o programa aberto. O painel acompanha o resultado e mostra detalhes de erros.
Só há uma instalação por vez; a atualização do programa aguarda sua conclusão.
O sucesso exige que o instalador termine sem erro e o recurso passe na verificação.

Verificar novamente refaz os testes. Fechar a caixa de diálogo não interrompe
a instalação. Se a Poda não conseguiu iniciar por falta de bibliotecas, reabra
a página após instalar, tomando cuidado com campos ainda não salvos. Não há
recarregamento automático que descarte seu trabalho.

Limitações: sem Python instalado o programa não consegue abrir esta interface;
use as instruções do iniciador para instalar Python primeiro. Arquivos ausentes
do editor PDF são corrigidos reaplicando uma atualização válida, não pelo pip.
Bloqueios corporativos não são contornados. O BAT permanece disponível como alternativa.

## Novidades do leitor

- Remover foto da lista exclui apenas a seleção de trabalho do leitor.
- Limpar todas as fotos pede confirmação e limpa a lista inteira.
- Essas ações não apagam os originais, as pastas organizadas nem fotos em books.
- É possível selecionar um ZIP, inclusive com fotos dentro de subpastas.
  Limites: 50 MB por ZIP, 100 fotos na lista, 18 MB por imagem e 200 MB no total
  das imagens descompactadas. ZIP com senha ou caminhos inseguros é recusado.
  Arquivos que não são JPG, PNG ou WebP são ignorados. Fotos inválidas são
  informadas, preservando as demais que foram lidas.
- Texto e GPS reconhecidos aparecem em um parágrafo contínuo, com quebra
  visual automática conforme a largura da tela, sem as quebras originais do OCR.

## Agrupamento por endereço

Escolha Por endereço reconhecido. O leitor procura o endereço no texto da foto.
Os grupos usam a mesma obra e o mesmo endereço normalizado: diferenças de
maiúsculas, acentos, pontuação e abreviações iniciais R./Rua e Av./Avenida não
separam um endereço. Números e cidades diferentes continuam separados.
Não é uma busca por proximidade de ruas nem uma consulta a mapas.

Revise rua, número, bairro e cidade antes de aplicar. Um endereço incompleto
pode não distinguir locais diferentes. Conflitos de pontos precisam de revisão.
Fotos sem coordenadas podem ser organizadas e anexadas quando possuem endereço.
Nesses casos, a coordenada fica vazia, sem geolocalização inventada. Para agrupar
por distância, continue usando o modo Por raio / coordenadas.

## Publicação e verificação

Coloque o ZIP em ZIPS do publicador, escolha o pacote e informe 1.6.2. Valide,
assine e publique os arquivos de ENVIAR_NO_GITHUB. Preserve a pasta dados.
Testes automatizados cobrem agrupamento, ZIP seguro, arquivos inválidos,
instaladores permitidos e falhas de validação. A interface foi conferida em
Chromium usando instalação simulada, sem baixar componentes no teste de tela.
A instalação nativa no Windows continua dependente da verificação no computador.
