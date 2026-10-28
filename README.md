# Operações Engelmig — Poda e Fechamento (v1.6.2)

Ao iniciar, escolha PODA ou FECHAMENTO. Poda reaproveita o programa Book Poda 12.5.0, com registros separados em dados/poda. Antes do primeiro uso de Poda, execute INSTALAR_RECURSOS_PODA.bat para instalar Pillow e ReportLab no Python utilizado pelo programa, sem administrador. Essa instalação requer internet.

Consulte docs/ATUALIZACAO_v1.6.2.md e docs/OPERACOES_v1.5.0.md. Google Earth Web abre em janela própria, pois bloqueia incorporação em páginas externas; a importação KML/KMZ continua disponível.

# Fechamento de Obras Engelmig

Aplicativo local para cadastrar obras, pontos, serviços e materiais, editar o croqui e gerar books.

## Iniciar

1. Extraia a instalação completa em uma pasta onde seu usuário possa gravar.
2. Abra **VERIFICAR_E_INICIAR.bat**, sem executar como administrador.
3. Mantenha a janela do programa aberta enquanto estiver usando o aplicativo.

Para iniciar diretamente quando o Python já estiver disponível, use **INICIAR.bat**. Para consultar problemas de instalação, use **VERIFICAR_INSTALACOES.bat**.

## Organização

| Pasta ou arquivo | Uso |
| --- | --- |
| `app.py` e módulos Python na raiz | Servidor local e funcionalidades do programa; não excluir. |
| `web/` | Interface, imagens e bibliotecas do editor PDF. |
| `data/` | Catálogos, composições, padrões e referências utilizados pelo programa. |
| `dados/` | Obras, fotos e configurações locais; criada durante o uso, fora do Git. |
| `fontes/` | As duas planilhas originais de mão de obra e materiais. |
| `modelos/` | Modelo de referência do book. |
| `tools/` | Ferramentas de importação, empacotamento e preparação de assinaturas. |
| `security/` | Verificador e, quando configurada, chave pública de atualização. Nunca guardar chave privada aqui. |
| `tests/` | Testes de regressão; necessários para desenvolvimento e validação. |
| `docs/` | Documentação atual e histórico das versões. |
| `runtime/` | Python local, quando utilizado; fora do Git. |
| `PREPARAR_PADROES.py` | Ferramenta para reunir exportações de materiais, mantida no caminho compatível. |

## Estado desta cópia de desenvolvimento

A última versão numerada nesta cópia é **1.6.2**. Há recursos de localização e melhorias de segurança preparados, ainda sem nova Release: consulte [Preparação de segurança](docs/SEGURANCA_PREPARACAO.md). Não distribua esta pasta como uma atualização pronta: a chave pública já está configurada, mas falta assinar o pacote no computador do publicador e validar o fluxo no Windows.

O GitHub permanece público. O campo separado para o repositório de materiais preserva o endereço atual enquanto estiver vazio; o novo repositório ainda não foi criado nem migrado.

## Documentação

- [Organização e limpeza](docs/ORGANIZACAO.md)
- [Preparação de segurança](docs/SEGURANCA_PREPARACAO.md)
- [Comandos Git](docs/GIT.txt)
- `docs/historico/`: instruções antigas, preservadas apenas como referência; não são o roteiro de publicação da próxima versão.

## Desenvolvimento

Execute na raiz: `python -m unittest discover -s tests`.

O arquivo `ATUALIZACAO.json` é um manifesto gerado dentro do ZIP de atualização. Não deve ser mantido manualmente na raiz nem reutilizado de uma versão anterior. A ferramenta `tools/criar_atualizacao.py` gera um manifesto novo para cada pacote.

Desenvolvido por Matheus Alves Araújo — matheusalvesaraujo540@gmail.com.
Os créditos são exibidos no aplicativo, não nos books e relatórios.
