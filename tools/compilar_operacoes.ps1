param([ValidateSet('photocraft','cadcraft','pdfcraft')][string[]]$Programs = @('photocraft','cadcraft','pdfcraft'))
$ErrorActionPreference = 'Stop'
$env:CARGO_BUILD_JOBS = '1'
$projectRoot = Split-Path $PSScriptRoot -Parent
$sourceRoot = Split-Path $projectRoot -Parent
$failed = @()
foreach ($program in $Programs) {
    if ($program -notmatch '^[a-z]+craft$') { throw 'Nome de operação inválido.' }
    $source = Join-Path $sourceRoot "$program/apps/$program-web"
    if (-not (Test-Path -LiteralPath (Join-Path $source 'Cargo.toml'))) {
        $failed += $program
        Write-Warning "Código web ausente: $program"
        continue
    }
    $destination = Join-Path $projectRoot "web/operations/$program"
    # MinGW não reconhece caminhos de saída com acentos no Windows.
    $cacheName = if ($program -in @('pdfcraft','cadcraft')) { $program } else { 'shared' }
    $env:CARGO_TARGET_DIR = Join-Path ([IO.Path]::GetTempPath()) "engelmig-web-build/$cacheName"
    Push-Location $source
    try {
        Write-Host "Compilando $program (CARGO_BUILD_JOBS=$env:CARGO_BUILD_JOBS)"
        & trunk build --release --public-url "./" --dist $destination
        if ($LASTEXITCODE -ne 0) { $failed += $program; continue }
        if (-not (Test-Path -LiteralPath (Join-Path $destination 'index.html')) -or
            -not (Get-ChildItem -LiteralPath $destination -Filter '*.wasm' -Recurse | Where-Object Length -gt 8)) {
            throw "Pacote incompleto: $program (index.html e wasm obrigatorios)."
        }
        Write-Host "Pacote gerado: $program"
        foreach ($notice in @('LICENSE-MIT','LICENSE-APACHE','NOTICE')) {
            $noticeSource = Join-Path (Join-Path $sourceRoot $program) $notice
            if (Test-Path -LiteralPath $noticeSource) { Copy-Item -LiteralPath $noticeSource -Destination $destination -Force }
        }
    } catch {
        $failed += $program
        Write-Warning "Falha em ${program}: $_"
    } finally { Pop-Location }
}
if ($failed.Count) { throw ('Operações não compiladas: ' + ($failed -join ', ')) }
