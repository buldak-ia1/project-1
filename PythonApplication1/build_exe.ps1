$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

python -m PyInstaller --clean --noconfirm MetaSortDesktop.spec

Write-Host ""
Write-Host "MetaSort EXE build completed:"
Write-Host (Join-Path $ProjectRoot "dist\MetaSort\MetaSort.exe")
