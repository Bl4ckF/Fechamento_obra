# Correção em preparação após a v1.3.8

O usuário relatou que a primeira tentativa não encerrou o aplicativo e a segunda concluiu a atualização.

Foi identificado um caminho em que uma falha ao responder ao navegador impede o agendamento do shutdown, apesar de o worker externo já ter sido iniciado. A correção usa finally para agendar o encerramento mesmo quando a resposta HTTP falha. Não encerra outros processos Python nem força o fechamento de aplicativos.

Teste de regressão cobre resposta normal, BrokenPipeError e ConnectionResetError. A causa do incidente real ainda depende do log da primeira tentativa.

Esta alteração existe apenas no código de desenvolvimento. O ZIP v1.3.8 assinado permanece byte a byte intacto. Antes de distribuir a correção, deve ser gerada uma nova versão e uma nova assinatura. A v1.3.8 não deve ser republicada com bytes diferentes.
