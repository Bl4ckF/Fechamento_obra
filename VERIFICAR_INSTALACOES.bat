@echo off
setlocal DisableDelayedExpansion
chcp 65001 >nul
title Engelmig - Verificar instalacoes
set "ENGELMIG_DIAG_FILE=%~f0"
set "ENGELMIG_DIAG_FOLDER=%~dp0"
set "ENGELMIG_DIAG_PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%ENGELMIG_DIAG_PS%" goto SEM_POWERSHELL
"%ENGELMIG_DIAG_PS%" -NoLogo -NoProfile -Command "$ErrorActionPreference='Stop'; try { $raw=[IO.File]::ReadAllText($env:ENGELMIG_DIAG_FILE); $parts=[regex]::Split($raw,'(?m)^#===ENGELMIG_DIAGNOSTICO_PS===\r?$'); if($parts.Length -ne 2){throw 'Arquivo de diagnostico incompleto.'}; & ([scriptblock]::Create($parts[1])) } catch { Write-Host ('FALHA NO VERIFICADOR: '+$_.Exception.Message) -ForegroundColor Red; exit 2 }"
set "ENGELMIG_DIAG_EXIT=%ERRORLEVEL%"
goto FINALIZAR
:SEM_POWERSHELL
echo [FALHA] O Windows PowerShell nao foi encontrado neste computador.
echo Este verificador foi preparado para Windows 10 ou 11.
echo Coloque este BAT na pasta do programa e execute em um Windows compativel.
set "ENGELMIG_DIAG_EXIT=2"
:FINALIZAR
echo.
if /I "%~1"=="/sem-pausa" goto SAIR
echo Pressione qualquer tecla para fechar.
pause >nul
:SAIR
endlocal & exit /b %ENGELMIG_DIAG_EXIT%
#===ENGELMIG_DIAGNOSTICO_PS===
# Um unico BAT. Esta parte usa o PowerShell que acompanha o Windows.
# Nao instala programas, nao autentica contas e nao envia registros.
$ErrorActionPreference = 'Stop'
$root = $env:ENGELMIG_DIAG_FOLDER
$script:lines = New-Object 'System.Collections.Generic.List[string]'
$script:failures = 0
$script:warnings = 0
$python = $null
$repository = 'https://github.com/Bl4ckF/fechamento_obra'
$syncBranch = 'registros-materiais'
$syncEnabled = $true
$dataDir = Join-Path $root 'dados'
if ($env:ENGELMIG_DATA_DIR) {
    if ([IO.Path]::IsPathRooted($env:ENGELMIG_DATA_DIR)) { $dataDir = $env:ENGELMIG_DATA_DIR }
    else { $dataDir = Join-Path $root $env:ENGELMIG_DATA_DIR }
}

function Report([string]$Level, [string]$Message) {
    $text = if ($Level) { '[{0}] {1}' -f $Level, $Message } else { $Message }
    $color = switch ($Level) { 'OK' {'Green'} 'FALHA' {'Red'} 'AVISO' {'Yellow'} default {'Gray'} }
    Write-Host $text -ForegroundColor $color
    $script:lines.Add($text)
    if ($Level -eq 'FALHA') { $script:failures++ }
    if ($Level -eq 'AVISO') { $script:warnings++ }
}

function NativeArgument([string]$Value) {
    # Quoting do Windows: conserva espacos, aspas e barras finais.
    $escaped = [regex]::Replace($Value, '(\\*)"', '$1$1\"')
    $escaped = [regex]::Replace($escaped, '(\\+)$', '$1$1')
    return '"' + $escaped + '"'
}

function InvokeCheck([string]$Executable, [string[]]$Arguments, [int]$Seconds = 15) {
    $process = New-Object System.Diagnostics.Process
    try {
        $info = New-Object System.Diagnostics.ProcessStartInfo
        $info.FileName = $Executable
        $info.Arguments = (($Arguments | ForEach-Object { NativeArgument $_ }) -join ' ')
        $info.WorkingDirectory = $root
        $info.UseShellExecute = $false
        $info.CreateNoWindow = $true
        $info.RedirectStandardOutput = $true
        $info.RedirectStandardError = $true
        $info.EnvironmentVariables['GIT_TERMINAL_PROMPT'] = '0'
        $info.EnvironmentVariables['GCM_INTERACTIVE'] = 'Never'
        $info.EnvironmentVariables['GH_PROMPT_DISABLED'] = '1'
        $info.EnvironmentVariables['GH_NO_UPDATE_NOTIFIER'] = '1'
        $info.EnvironmentVariables['PYTHON_MANAGER_AUTOMATIC_INSTALL'] = 'false'
        $info.EnvironmentVariables.Remove('PYLAUNCHER_ALLOW_INSTALL')
        $info.EnvironmentVariables['PYTHONIOENCODING'] = 'utf-8'
        $info.StandardOutputEncoding = [Text.Encoding]::UTF8
        $info.StandardErrorEncoding = [Text.Encoding]::UTF8
        $process.StartInfo = $info
        [void]$process.Start()
        $stdout = $process.StandardOutput.ReadToEndAsync()
        $stderr = $process.StandardError.ReadToEndAsync()
        if (-not $process.WaitForExit($Seconds * 1000)) {
            try { $process.Kill() } catch {}
            return [pscustomobject]@{ Code = -1; Out = ''; Error = 'Tempo de resposta esgotado.' }
        }
        # Nao registra stderr dos comandos de autenticacao: pode conter dados da conta.
        $output = if ($stdout.Wait(2000)) { $stdout.Result.Trim() } else { '' }
        return [pscustomobject]@{ Code = $process.ExitCode; Out = $output; Error = '' }
    } catch {
        return [pscustomobject]@{ Code = -1; Out = ''; Error = 'Nao foi possivel executar o comando.' }
    } finally { $process.Dispose() }
}

function FindCommand([string]$Name) {
    $command = Get-Command $Name -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($command) { return $command.Source }
    return $null
}

Report '' 'ENGELMIG - VERIFICACAO DE INSTALACOES'
Report '' ('Data: ' + (Get-Date -Format 'dd/MM/yyyy HH:mm:ss'))
Report '' ('Pasta: ' + $root)
Report '' 'O diagnostico faz consultas e cria este relatorio. Nao instala nem publica arquivos.'
Report '' ''
Report 'OK' ('Windows PowerShell ' + $PSVersionTable.PSVersion.ToString())

try {
    Report '' '1. PYTHON E BIBLIOTECAS DO PROGRAMA'
    $candidates = @()
    $bundled = Join-Path $root 'runtime\python.exe'
    if (Test-Path -LiteralPath $bundled -PathType Leaf) {
        $candidates += [pscustomobject]@{ File=$bundled; Prefix=@(); Label='Python da pasta runtime' }
    }
    $py = FindCommand 'py.exe'
    if ($py) { $candidates += [pscustomobject]@{ File=$py; Prefix=@('-3'); Label='py -3' } }
    $onPath = FindCommand 'python.exe'
    if ($onPath) { $candidates += [pscustomobject]@{ File=$onPath; Prefix=@(); Label='python no PATH' } }
    $probe = @'
import sys,json
print(json.dumps({'version':list(sys.version_info[:3]),'executable':sys.executable,'bits':64 if sys.maxsize>2**32 else 32}))
'@
    foreach ($candidate in $candidates) {
        $check = InvokeCheck $candidate.File (@($candidate.Prefix) + @('-c', $probe))
        if ($check.Code -ne 0) {
            Report 'AVISO' ($candidate.Label + ' nao respondeu como interpretador Python. Pode ser apenas o atalho da Microsoft Store.')
            continue
        }
        try { $details = $check.Out | ConvertFrom-Json } catch { continue }
        if (($details.version[0] -lt 3) -or (($details.version[0] -eq 3) -and ($details.version[1] -lt 9))) {
            Report 'AVISO' ($candidate.Label + ' e antigo: ' + ($details.version -join '.') + '. O programa requer Python 3.9 ou superior.')
            continue
        }
        $python = $candidate
        Report 'OK' ('Python ' + ($details.version -join '.') + ' - ' + $details.bits + ' bits')
        Report 'INFO' ('Interpretador: ' + $details.executable)
        break
    }
    if (-not $python) {
        Report 'FALHA' 'Python 3.9 ou superior nao encontrado pelos comandos usados no INICIAR.bat.'
        Report 'COMO CORRIGIR' 'Instale o Python: https://www.python.org/downloads/windows/'
        Report 'COMO CORRIGIR' 'No instalador tradicional, marque Add Python to PATH. Feche e reabra este verificador apos instalar.'
    } else {
        if ((Test-Path -LiteralPath $bundled) -and ($python.File -ne $bundled)) {
            Report 'FALHA' 'Ha um runtime\python.exe invalido ou antigo. O INICIAR.bat prioriza essa copia; revise a pasta runtime.'
        }
        $modules = @'
import json,sqlite3,ssl,threading,http.server,urllib.request,secrets,uuid,webbrowser,csv,hashlib,decimal,subprocess
db=sqlite3.connect(':memory:'); assert db.execute('select 1').fetchone()[0]==1; db.close()
print(json.dumps({'sqlite':sqlite3.sqlite_version,'ssl':ssl.OPENSSL_VERSION}))
'@
        $check = InvokeCheck $python.File (@($python.Prefix) + @('-c', $modules))
        if ($check.Code -eq 0) {
            $details = $check.Out | ConvertFrom-Json
            Report 'OK' ('Bibliotecas obrigatorias, banco SQLite ' + $details.sqlite + ' e suporte SSL disponiveis.')
        } else {
            Report 'FALHA' 'O Python foi encontrado, mas faltam bibliotecas padrao ou o SQLite/SSL nao funciona. Repare a instalacao completa do Python.'
        }
        Report 'INFO' 'Este programa nao precisa de pip, Node.js nem pacotes Python adicionais.'
        $database = Join-Path $dataDir 'fechamento.sqlite3'
        if (Test-Path -LiteralPath $database -PathType Leaf) {
            $readSettings = @'
import sqlite3,json,sys,pathlib
db=sqlite3.connect(pathlib.Path(sys.argv[1]).resolve().as_uri()+'?mode=ro',uri=True,timeout=2)
exists=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='settings'").fetchone()
row=db.execute("SELECT payload FROM settings WHERE id='config'").fetchone() if exists else None
data=json.loads(row[0]) if row else {}; db.close()
print(json.dumps({key:data[key] for key in ('repository','sync_branch','sync_enabled') if key in data}))
'@
            $check = InvokeCheck $python.File (@($python.Prefix) + @('-c', $readSettings, $database))
            if ($check.Code -eq 0) {
                $saved = $check.Out | ConvertFrom-Json
                if ($saved.repository -match '^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/?$') { $repository = $saved.repository.TrimEnd('/') }
                if ($saved.sync_branch -match '^[A-Za-z0-9][A-Za-z0-9_/-]*$') { $syncBranch = $saved.sync_branch }
                if ($saved.sync_enabled -eq $false) { $syncEnabled = $false }
                Report 'OK' 'Configuracoes existentes consultadas em modo de leitura.'
            } else { Report 'AVISO' 'Nao foi possivel ler as configuracoes locais. O teste usara o repositorio padrao.' }
        }
    }

    Report '' ''
    Report '' '2. GIT E ACESSO AO REPOSITORIO'
    $git = FindCommand 'git.exe'
    if (-not $git) {
        Report 'AVISO' 'Git nao encontrado. O programa pode funcionar localmente, mas somente a sincronizacao dos registros depende dele. Atualizacoes usam Releases.'
        Report 'COMO CORRIGIR' 'Instale o Git para Windows, incluindo Git Credential Manager: https://git-scm.com/downloads/win'
    } else {
        $check = InvokeCheck $git @('--version')
        if ($check.Code -eq 0) { Report 'OK' $check.Out }
        else { Report 'AVISO' 'Git encontrado, mas nao foi possivel executa-lo.' }
        $gcm = InvokeCheck $git @('credential-manager','--version')
        if ($gcm.Code -eq 0) { Report 'OK' 'Git Credential Manager disponivel para gerenciar o login.' }
        else { Report 'INFO' 'Git Credential Manager nao detectado. Outra forma de autenticar o Git pode estar configurada.' }
        Report 'INFO' ('Repositorio verificado: ' + $repository)
        Report 'INFO' ('Branch dos registros: ' + $syncBranch)
        if (-not $syncEnabled) { Report 'AVISO' 'A sincronizacao automatica esta desativada nas Configuracoes do programa.' }
        $remote = InvokeCheck $git @('-c','http.lowSpeedLimit=1','-c','http.lowSpeedTime=15','ls-remote',$repository,'HEAD') 30
        if ($remote.Code -eq 0) {
            Report 'OK' 'O Git conseguiu acessar o repositorio para leitura.'
            Report 'INFO' 'Leitura de um repositorio publico nao confirma login nem permissao de escrita.'
        } else {
            Report 'AVISO' 'Nao foi possivel ler o repositorio. Confira internet, proxy/firewall, endereco e credencial de acesso.'
        }
    }

    Report '' ''
    Report '' '3. AUTENTICACAO GITHUB - VERIFICACAO OPCIONAL'
    $gh = FindCommand 'gh.exe'
    if ($gh) {
        $auth = InvokeCheck $gh @('auth','status','--hostname','github.com') 20
        if ($auth.Code -eq 0) {
            Report 'OK' 'GitHub CLI autenticado.'
            $repoName = $repository.Substring('https://github.com/'.Length) -replace '\.git$',''
            $permission = InvokeCheck $gh @('api',('repos/' + $repoName),'--jq','.permissions.push') 20
            if (($permission.Code -eq 0) -and ($permission.Out -eq 'true')) {
                Report 'OK' 'A conta ativa do GitHub CLI tem permissao de escrita neste repositorio.'
                Report 'INFO' 'O Git pode usar outra credencial. Para usar a conta do CLI no Git, execute: gh auth setup-git'
            } elseif (($permission.Code -eq 0) -and ($permission.Out -eq 'false')) {
                Report 'AVISO' 'A conta ativa do GitHub CLI nao tem permissao de escrita no repositorio.'
            } else { Report 'AVISO' 'Nao foi possivel confirmar a permissao de escrita pela API do GitHub.' }
        } else {
            Report 'AVISO' 'O GitHub CLI nao confirmou uma autenticacao valida. Isso nao invalida um login separado pelo Git Credential Manager.'
            Report 'COMO CORRIGIR' 'Se for usar o CLI, execute: gh auth login'
            Report 'COMO CORRIGIR' 'Depois execute: gh auth setup-git'
        }
    } else {
        Report 'INFO' 'GitHub CLI nao instalado. Ele e opcional se o Git ja usa outra credencial valida.'
        Report 'INFO' 'Opcao de autenticacao: instale https://cli.github.com e execute gh auth login e gh auth setup-git.'
        Report 'INFO' 'Sem o CLI, este diagnostico nao confirma a permissao de escrita da conta.'
    }
    Report 'INFO' 'A confirmacao final do envio e feita no programa: Configuracoes > Sincronizar agora.'
    Report 'INFO' 'Nenhum commit ou push foi executado por este verificador.'

    Report '' ''
    Report '' '4. ARQUIVOS DO PROGRAMA'
    $required = @('INICIAR.bat','app.py','engine.py','pricing.py','compositions.py','book.py','book_report.py',
        'drawing.py','symbols.py','learning.py','records_sync.py','geo.py','updates.py','version.json',
        'data\catalogos.json','data\composicoes_material.json','data\qfield_equipment_index.json',
        'web\index.html','web\app.js','web\book.js','web\drawing.js','web\learning.js',
        'web\croqui-pages.js','web\croqui-pdf-export.js','web\vendor\pdf-lib\pdf-lib.min.js',
        'web\drawing-ui.js','web\drawing-transform.js','web\symbol-editor.js','web\pdf-search.js','web\croqui-render.js','web\croqui-render-worker.js','web\pdf-lines.js','web\pdf-source.js','web\pdf-background.js','web\network-symbols.js','web\croqui-quality.js','data\simbolos_rede.json','web\pdf-text.js','web\records-sync.js','web\style.css','web\book.css','web\v4.css',
        'web\assets\engelmig.png','web\map_v11.html','web\map_v11.js','web\qfield_manifest.js',
        'web\vendor\pdfjs\pdf.min.mjs','web\vendor\pdfjs\pdf.worker.min.mjs',
        'web\vendor\pdfjs\standard_fonts\LiberationSans-Regular.ttf','web\vendor\pdfjs\wasm\openjpeg.wasm')
    $missing = @($required | Where-Object { -not (Test-Path -LiteralPath (Join-Path $root $_) -PathType Leaf) })
    if ($missing.Count -eq 0) { Report 'OK' 'Arquivos principais do programa, do mapa e da leitura de PDF encontrados.' }
    else {
        Report 'FALHA' 'Arquivos ausentes ou BAT fora da pasta do programa. Coloque este BAT ao lado de INICIAR.bat e extraia o ZIP completo.'
        foreach ($item in $missing) { Report 'FALTA' $item }
    }

    Report '' ''
    Report '' '5. GRAVACAO E PORTAS LOCAIS'
    $probeFile = $null
    try {
        [void][IO.Directory]::CreateDirectory($dataDir)
        $probeFile = Join-Path $dataDir ('diagnostico_' + [guid]::NewGuid().ToString('N') + '.tmp')
        [IO.File]::WriteAllText($probeFile, 'Teste temporario de gravacao.')
        [IO.File]::Delete($probeFile)
        Report 'OK' 'Permissao de gravacao na pasta de dados confirmada.'
    } catch { Report 'FALHA' 'Sem permissao de gravacao na pasta de dados. Use uma pasta do seu usuario com permissao de escrita.' }
    finally { if ($probeFile -and [IO.File]::Exists($probeFile)) { try { [IO.File]::Delete($probeFile) } catch {} } }
    $available = $null
    foreach ($port in 8766..8775) {
        $listener = $null
        try {
            $listener = [System.Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, [int]$port)
            $listener.Start(); $available = $port; break
        } catch {} finally { if ($listener) { $listener.Stop() } }
    }
    if ($null -ne $available) { Report 'OK' ('Porta local disponivel para iniciar o servidor: ' + $available) }
    else { Report 'AVISO' 'Portas 8766 a 8775 ocupadas ou bloqueadas. O programa pode ja estar aberto.' }

} catch {
    Report 'FALHA' ('A verificacao foi interrompida: ' + $_.Exception.Message)
}

Report '' ''
Report '' 'RESULTADO'
Report '' ('Falhas para abrir o programa: ' + $failures + ' | Avisos: ' + $warnings)
if ($failures -eq 0) { Report 'OK' 'Requisitos basicos verificados. Abra INICIAR.bat e confira a sincronizacao em Configuracoes.' }
else { Report 'INFO' 'Corrija as falhas indicadas e execute este verificador novamente.' }
Report 'INFO' 'Mantenha a pasta dados ao atualizar. Nao precisa executar este BAT como administrador.'

$logName = 'DIAGNOSTICO_INSTALACOES_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.txt'
$log = Join-Path $root $logName
try {
    [IO.File]::WriteAllLines($log, $lines.ToArray(), [Text.UTF8Encoding]::new($true))
    Write-Host ('Relatorio salvo em: ' + $log) -ForegroundColor Cyan
} catch {
    $log = Join-Path ([IO.Path]::GetTempPath()) $logName
    try {
        [IO.File]::WriteAllLines($log, $lines.ToArray(), [Text.UTF8Encoding]::new($true))
        Write-Host ('Relatorio salvo na pasta temporaria: ' + $log) -ForegroundColor Cyan
    } catch { Write-Host 'Nao foi possivel salvar o relatorio. Consulte as mensagens acima.' -ForegroundColor Yellow }
}
if ($failures -gt 0) { exit 1 }
exit 0
