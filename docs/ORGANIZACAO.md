# Organização e limpeza do projeto

## Alterações feitas nesta cópia

- Manuais transferidos para docs/, separando o histórico v1.3.7 das instruções atuais.
- README.md atualizado como ponto de entrada para iniciar e entender as pastas.
- Removidos o diagnóstico de 19/10/2026, a saída de terminal chamada cls e os caches Python.
- Retirado o ATUALIZACAO.json antigo da raiz. O empacotador continua gerando o manifesto dentro do pacote.
- Regras de exclusão do Git ampliadas para arquivos temporários, runtime, diagnósticos e chaves privadas.
- O empacotador não inclui os antigos manuais da raiz nem exige sua presença na base para gerar um pacote cumulativo.

Uma cópia dos arquivos alterados/removidos foi guardada fora da pasta do projeto antes da limpeza. Nada foi apagado do histórico remoto do GitHub. O .gitignore não remove arquivos que já tenham sido publicados anteriormente.

## Compatibilidade

Os módulos Python e os três iniciadores BAT foram mantidos na raiz porque os iniciadores, importações e atualizador dependem desses caminhos. As planilhas de fontes/, o modelo de modelos/, os catálogos de data/ e as bibliotecas de web/vendor/ foram preservados.

A limpeza ocorreu na cópia de desenvolvimento. Nenhum comando foi executado no computador do usuário, nenhuma alteração foi enviada ao GitHub e nenhuma Release foi publicada.

Atualizações incrementais existentes preservam arquivos ausentes do ZIP. Portanto, mover um manual nesta cópia não apaga a versão antiga dele nos computadores. Uma futura limpeza das instalações deve tratar apenas arquivos conhecidos, sem apagar dados, credenciais ou documentos personalizados.
