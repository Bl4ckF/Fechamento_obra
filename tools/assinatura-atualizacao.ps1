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
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $package = [IO.Compression.ZipFile]::OpenRead($Zip)
    try {
        $entry = $package.GetEntry('Fechamento_Obras_Engelmig/security/update-public.xml')
        if (!$entry) { throw 'Pacote sem chave publica.' }
        $reader = New-Object IO.StreamReader($entry.Open())
        try { [xml]$trusted = $reader.ReadToEnd() } finally { $reader.Dispose() }
        [xml]$own = $rsa.ToXmlString($false)
        if ($trusted.RSAKeyValue.Modulus -ne $own.RSAKeyValue.Modulus -or $trusted.RSAKeyValue.Exponent -ne $own.RSAKeyValue.Exponent) {
            throw 'A chave privada deste computador nao corresponde a chave publica do pacote.'
        }
        $entry = $package.GetEntry('Fechamento_Obras_Engelmig/version.json')
        if (!$entry) { throw 'Pacote sem versao.' }
        $reader = New-Object IO.StreamReader($entry.Open())
        try { $meta = $reader.ReadToEnd() | ConvertFrom-Json } finally { $reader.Dispose() }
        if ($meta.version -ne $Versao) { throw 'Versao informada difere da versao do ZIP.' }
    } finally { $package.Dispose() }
    $sha = (Get-FileHash -LiteralPath $Zip -Algorithm SHA256).Hash.ToLowerInvariant()
    $message = [Text.Encoding]::UTF8.GetBytes("Engelmig-update-v1`n$Versao`n$sha`n")
    $signature = [Convert]::ToBase64String($rsa.SignData($message, 'SHA256'))
    if (!$rsa.VerifyData($message, 'SHA256', [Convert]::FromBase64String($signature))) { throw 'Falha na verificacao da assinatura gerada.' }
    $metadata = @{ algorithm='RSA-SHA256'; version=$Versao; sha256=$sha; signature=$signature } | ConvertTo-Json
    [IO.File]::WriteAllText("$Zip.sig.json", $metadata, (New-Object Text.UTF8Encoding($false)))
    Write-Host "Publique juntos: $Zip e $Zip.sig.json"
} catch { Write-Host ('Falha: ' + $_.Exception.Message); exit 1 } finally { $rsa.Dispose() }
