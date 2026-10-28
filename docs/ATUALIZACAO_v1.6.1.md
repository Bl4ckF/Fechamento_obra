# Atualização 1.6.1

## Instalação do leitor corrigida

O RapidOCR 1.4.4 não aceita Python 3.13/3.14. O aplicativo pode continuar no
Python 3.14: agora chama um ambiente separado para reconhecer as imagens.

Após instalar esta atualização, execute INSTALAR_LEITOR_FOTOS.bat novamente.
O instalador procura Python 3.9 a 3.12 de 64 bits. Se não houver, tenta obter
Python 3.12 com o gerenciador oficial Python Install Manager, para o usuário.
Cria o ambiente em %LOCALAPPDATA%\Engelmig\ocr-python312 e instala/verifica
os recursos. Não remove o Python atual nem altera o iniciador do programa.
Internet é necessária para instalar; fotos são processadas localmente.

Se o gerenciador não existir ou houver bloqueio corporativo, a instalação
para com uma orientação: instalar Python 3.12 de 64 bits para o usuário e
repetir o BAT. Não requer instalação para todos os usuários nem altera
políticas de execução. Não informa sucesso quando uma etapa falha.

Reinicie o programa após a mensagem de sucesso. O novo ambiente fica fora
da pasta do projeto, sendo preservado nas atualizações.

## Agrupar fotos por raio

Depois da leitura, a prévia separa fotos da mesma obra por proximidade.
Ajuste a barra entre 5 e 500 metros (padrão: 25 m). O raio é medido a partir
da foto de referência de cada grupo; uma cadeia de fotos próximas não une
extremos distantes. Fotos sem obra ou coordenada válida ficam fora.

Confira a quantidade, os nomes das fotos e o ponto sugerido em cada grupo.
Se houver pontos reconhecidos diferentes no mesmo grupo, defina o correto.
Se o mesmo ponto surgir em grupos distantes, revise seus nomes. O programa
não aplica grupos conflitantes ou com nomes repetidos na mesma obra.

Clique em Aplicar pontos sugeridos. Isso preenche o campo ponto das fotos,
sem mover ou apagar arquivos. Marque a conferência antes de Criar pastas e
copiar fotos ou Adicionar à obra atual. Para as fotos sem número, são sugeridos
G01, G02 etc.; troque esses nomes pelo número real do ponto se necessário.

## Interface e tutorial

Fechamento usa cartões, espaçamentos e navegação próximos à operação Poda,
com identidade própria azul e cobre. Campos, registros, revisão, configurações
e leitura de fotos seguem o mesmo visual. Os condutores ficam em um painel
recolhível de Pontos e serviços, antes do botão de continuar. Novos pontos
aparecem imediatamente na seleção dos trechos.

O tutorial esclarece: PODA confecciona books de poda e LF (Limpeza de Faixa);
FECHAMENTO confecciona books de obras. Use o botão Tutorial para rever.
A preferência de primeiro acesso continua preservada. PDFs e books não
recebem marca d'água do desenvolvedor.

## Publicação

Coloque o ZIP em ZIPS do publicador, selecione-o e informe 1.6.1. Valide e
assine com sua chave. Publique os arquivos de ENVIAR_NO_GITHUB na Release.
O pacote é cumulativo a partir de 1.3.5 e preserva dados. Nenhuma chave privada
é incluída. Faça cópia da pasta dados antes de atualizar.

## Verificação

Testes de extração, limites, agrupamento, conflitos, proteção de arquivos,
instalador e integração do worker. OCR real verificado com foto sintética.
Fluxo visual testado em Chromium com tráfego externo bloqueado, usando OCR
simulado apenas na interface. O BAT e a obtenção de Python pelo gerenciador
precisam de conferência no computador Windows; não foram executados nativamente
no ambiente de desenvolvimento.
