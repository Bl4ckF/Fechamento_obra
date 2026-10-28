# Preparação da próxima atualização — não publicar ainda

Candidato v1.3.8, com chave pública RSA 3072 bits recebida do publicador. A assinatura final e a validação nativa no Windows ainda precisam ocorrer no computador do publicador antes da distribuição.

Implementado:
- Release exige ZIP e arquivo de assinatura com o mesmo nome acrescido de .sig.json.
- RSA de pelo menos 3072 bits, SHA256, verificação via Windows CNG/bcrypt.dll, sem executar scripts PowerShell nos computadores da equipe.
- Assinatura vincula versão e hash de todo o ZIP. A chave confiável vem da instalação local, nunca da Release consultada.
- O processo instalador confere novamente o hash recebido do processo verificador e rejeita downgrade/reinstalação da mesma versão.
- Validação comum de caminhos, duplicados sem distinção de maiúsculas, nomes reservados do Windows e destinos que escapam da instalação por links.
- Campo records_repository separado, vazio preserva a configuração atual. Nenhum repositório remoto é criado automaticamente, e nenhuma credencial é alterada.
- Restauração existente testada com falha simulada; falhas na própria restauração deixam erro explícito e indicam a pasta do backup.

Próximos passos necessários:
1. No computador do publicador, executar tools/CRIAR_CHAVE_PUBLICACAO.bat. Não requer administrador. Políticas corporativas de PowerShell podem impedir a execução; pedir liberação ao TI, não contornar a política.
2. CONCLUÍDO: chave pública instalada em security/update-public.xml. A chave privada DPAPI fica em %LOCALAPPDATA%/EngelmigPublicacao vinculada ao usuário Windows. Não enviar, não incluir no Git, ZIP ou backup público. Planejar backup seguro e recuperação da chave antes da produção.
3. Testar no Windows assinatura válida, assinatura adulterada, reinício e preservação dos dados. O ambiente de desenvolvimento Linux não executou o provedor criptográfico Windows.
4. Versão alinhada em 1.3.8. O kit inclui um BAT para assinar e validar antes de publicar. Para assinatura manual: powershell -NoProfile -File tools/assinatura-atualizacao.ps1 -Zip CAMINHO_DO_ZIP -Versao X.Y.Z.
5. Publicar ZIP e ZIP.sig.json juntos. A primeira instalação usa a confiança no atualizador antigo; a proteção criptográfica passa a valer para as próximas atualizações. Não prometer validação retroativa.
6. Criar o repositório de materiais, transferir o histórico e conferir permissões antes de trocar records_repository nos computadores. Só uma branch diferente não isola permissões de escrita no código.

Não implementados nesta etapa: cadastro/login, acesso remoto, criptografia dos dados locais, backup externo dos dados, verificação de saúde automática após reinício e rotação de chaves. A assinatura não impede alteração por alguém que já controla a conta Windows e os arquivos do programa. Não é uma implementação completa do protocolo TUF.

Os books continuam sem créditos do desenvolvedor. Não houve publicação de Release nem alteração de permissões do GitHub.
