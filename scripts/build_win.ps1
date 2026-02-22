$ErrorActionPreference = "Stop"

Set-Location (Resolve-Path "$PSScriptRoot\..")

$version = & python scripts/get_version.py
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($version)) {
    $version = & py -3 scripts/get_version.py
}
if ([string]::IsNullOrWhiteSpace($version)) {
    throw "Could not determine version."
}

python scripts/set_version.py
python -m PyInstaller --noconfirm MainApp.spec

$iscc = $env:ISCC_PATH
if ([string]::IsNullOrWhiteSpace($iscc)) {
    $iscc = "ISCC.exe"
}

& $iscc installer.iss /DMyAppVersion=$version

$outDir = Join-Path (Get-Location) "dist\\installer"
$fixed = Join-Path $outDir "TipSplit-Setup.exe"
$versioned = Join-Path $outDir ("TipSplit-Setup-{0}.exe" -f $version)
if (Test-Path $fixed) {
    Copy-Item -Path $fixed -Destination $versioned -Force
}

Write-Host "Created Windows installer in dist\\installer"
