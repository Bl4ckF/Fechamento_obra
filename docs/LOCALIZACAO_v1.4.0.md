# v1.4.0 — Localização e Google Earth

Esta versão inclui a correção de encerramento prevista para a v1.3.9; não é necessário publicar uma versão intermediária.

## Uso

1. Abra Localização / Google Earth.
2. Digite endereço com cidade/estado. Após uma pausa de um segundo, aparecem sugestões aproximadas do Photon/OpenStreetMap. O texto digitado é enviado a esse serviço público. Não digite informações sigilosas. O provedor não garante disponibilidade; a aplicação informa quando a busca falha.
3. Selecione um resultado ou informe latitude e longitude. Confira a UTM (datum WGS84, fuso/faixa correspondentes; por exemplo 21K). Use o link de conferência para abrir OpenStreetMap no navegador, se desejar.
4. Aplique ao ponto ativo ou crie um ponto novo. Mão de obra, materiais e referências elétricas continuam sendo preenchidos/conferidos pelo usuário.
5. Exporte os elementos do Google Earth para KML ou KMZ e importe o arquivo. Marcadores, linhas e áreas ficam armazenados na obra, inclusive contornos internos de áreas. Elementos repetidos idênticos não são duplicados.
6. Na prévia, use a roda para ampliar e arraste para navegar. Clique para selecionar uma coordenada. Ver / selecionar início escolhe o marcador ou o primeiro vértice de uma linha/área.
7. Adicionar prévia ao croqui cria uma NOVA página de imagem, sem substituir páginas existentes. É uma referência geográfica sem escala técnica; os traços não se tornam objetos vetoriais editáveis no croqui. As geometrias originais continuam na aba Localização.

## Limites e preservação

- KML/KMZ até 10 MB; KMZ até 20 MB descompactado, 200 entradas e 10 documentos KML.
- Até 500 geometrias e 20.000 vértices por obra.
- UTM cobre de 80° S a 84° N. Coordenadas fora dessa faixa são recusadas na importação.
- Altitudes, estilos, ícones, fotos, sobreposições, links externos e trilhas animadas não são importados. Arquivos compactados não são extraídos para o disco.
- Não há sincronização ao vivo com o Google Earth. Reexporte e importe um arquivo para trazer alterações.
- Prévia geográfica local sem ruas ou satélite. Não é uma ferramenta de levantamento topográfico.
- KML/KMZ e conversão de coordenadas funcionam offline. Endereços e o link de mapa externo precisam de internet.
- Nenhum arquivo de obra é enviado ao provedor de endereços ou ao GitHub por este recurso.
- A visualização QField foi retirada e suas antigas páginas HTTP retornam 404. Referências elétricas locais existentes foram preservadas para consulta por coordenada nos pontos.

## Atualização

Pacote cumulativo baseado na instalação completa v1.3.5. Pode atualizar v1.3.5–v1.3.8. Inclui a chave pública já validada. O publicador deve assinar o ZIP exato e publicar também o arquivo .zip.sig.json. Não reaproveitar a assinatura da v1.3.8.

A correção de encerramento agenda o shutdown mesmo se a resposta HTTP ao navegador falhar depois de iniciar o worker. Não encerra à força outros processos Python.

Nada foi publicado automaticamente no GitHub. O fluxo nativo de assinatura Windows foi validado anteriormente na v1.3.8; o novo pacote precisa de nova assinatura e teste de instalação.
