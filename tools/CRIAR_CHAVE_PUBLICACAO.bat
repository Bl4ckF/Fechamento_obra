@echo off
setlocal DisableDelayedExpansion
title Engelmig - Gerar chave de publicacao
set "ENGELMIG_KEY_BAT=%~f0"
echo Este arquivo gera a chave de assinatura das atualizacoes.
echo Nao precisa de administrador e nao altera a politica permanente.
echo A chave privada fica protegida pela sua conta Windows.
echo.
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -Command "$ErrorActionPreference='Stop'; $temp=$null; try { $pol=Get-ExecutionPolicy -List; $group=@($pol | Where-Object { ($_.Scope -eq 'MachinePolicy' -or $_.Scope -eq 'UserPolicy') -and $_.ExecutionPolicy -ne 'Undefined' }); if ($group.Count) { throw 'Existe politica corporativa configurada. Solicite avaliacao ao TI.' }; $defined=@($pol | Where-Object { $_.ExecutionPolicy -ne 'Undefined' -and $_.ExecutionPolicy -ne 'RemoteSigned' }); if ($defined.Count) { throw 'Existe politica explicita de execucao. Ela nao sera alterada. Solicite avaliacao ao TI.' }; $text=[IO.File]::ReadAllText($env:ENGELMIG_KEY_BAT); $mark='###'+'ENGELMIG_POWERSHELL###'; $index=$text.IndexOf($mark); if ($index -lt 0) { throw 'BAT incompleto.' }; $body=$text.Substring($index+$mark.Length); $temp=Join-Path $env:TEMP ('engelmig-key-'+[guid]::NewGuid().ToString('N')+'.ps1'); [IO.File]::WriteAllText($temp,$body,(New-Object Text.UTF8Encoding($false))); & ($PSHOME+'\powershell.exe') -NoProfile -NonInteractive -ExecutionPolicy RemoteSigned -File $temp -CriarChave; $code=$LASTEXITCODE; if ($code -ne 0) { throw ('Falha na geracao. Codigo '+$code) }; exit 0 } catch { Write-Host ('ERRO: '+$_.Exception.Message); exit 1 } finally { if ($temp -and (Test-Path -LiteralPath $temp)) { Remove-Item -LiteralPath $temp -Force } }"
if errorlevel 1 goto erro
echo.
echo Pronto. Envie SOMENTE update-public.xml.
echo NAO envie chave-privada.dpapi.xml.
explorer.exe /select,"%LOCALAPPDATA%\EngelmigPublicacao\update-public.xml"
pause
exit /b 0
:erro
echo.
echo Nenhuma politica permanente foi alterada.
echo Copie a mensagem acima para verificarmos o problema.
pause
exit /b 1
###ENGELMIG_POWERSHELL###
param(
    [switch]$CriarChave,
    [string]$Zip,
    [string]$Versao,
    [string]$PastaChaves = "$env:LOCALAPPDATA\EngelmigPublicacao"
)
$ErrorActionPreference = 'Stop'
$rsa = New-Object System.Security.Cryptography.RSACryptoServiceProvider(3072)
$rsa.PersistKeyInCsp = $false
try {
    $privatePath = Join-Path $PastaChaves 'chave-privada.dpapi.xml'
    $publicPath = Join-Path $PastaChaves 'update-public.xml'
    if ($CriarChave) {
        if (Test-Path $privatePath) {
            $stored = Import-Clixml -LiteralPath $privatePath
            $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($stored)
            try { $rsa.FromXmlString([Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)) }
            finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
            if ($rsa.KeySize -lt 3072) { throw 'A chave existente tem tamanho insuficiente. Nao sera substituida.' }
            [IO.File]::WriteAllText($publicPath, $rsa.ToXmlString($false))
            Write-Host "Chave existente preservada. Envie SOMENTE: $publicPath"
            exit 0
        }
        New-Item -ItemType Directory -Force -Path $PastaChaves | Out-Null
        $probe = [Text.Encoding]::UTF8.GetBytes('Engelmig signature self-test')
        $testSignature = $rsa.SignData($probe, 'SHA256')
        if (!$rsa.VerifyData($probe, 'SHA256', $testSignature)) { throw 'Falha no teste criptografico.' }
        # DPAPI protege a chave para o usuario atual do Windows. Nunca enviar este arquivo.
        $secret = ConvertTo-SecureString -String $rsa.ToXmlString($true) -AsPlainText -Force
        $secret | Export-Clixml -Path $privatePath
        [IO.File]::WriteAllText($publicPath, $rsa.ToXmlString($false))
        Write-Host "Chave criada. Envie SOMENTE: $publicPath"
        Write-Host 'A chave privada fica vinculada a esta conta do Windows. Preserve esta conta e este computador.'
        exit 0
    }
    if ($Versao -notmatch '^\d+\.\d+\.\d+$') { throw 'Informe -Versao X.Y.Z.' }
    $Zip = (Resolve-Path -LiteralPath $Zip).Path
    $secret = Import-Clixml -LiteralPath $privatePath
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
    try { $rsa.FromXmlString([Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
    $sha = (Get-FileHash -LiteralPath $Zip -Algorithm SHA256).Hash.ToLowerInvariant()
    $message = [Text.Encoding]::UTF8.GetBytes("Engelmig-update-v1`n$Versao`n$sha`n")
    $signature = [Convert]::ToBase64String($rsa.SignData($message, 'SHA256'))
    $metadata = @{ algorithm='RSA-SHA256'; version=$Versao; sha256=$sha; signature=$signature } | ConvertTo-Json
    [IO.File]::WriteAllText("$Zip.sig.json", $metadata, (New-Object Text.UTF8Encoding($false)))
    Write-Host "Publique juntos: $Zip e $Zip.sig.json"
} catch { Write-Host ('Falha: ' + $_.Exception.Message); exit 1 } finally { $rsa.Dispose() }
