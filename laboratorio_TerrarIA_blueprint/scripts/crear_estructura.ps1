$ErrorActionPreference = "Stop"

$source = Split-Path -Parent $PSScriptRoot
$target = "E:\laboratorio_TerrarIA"

if (Test-Path $target) {
    $items = Get-ChildItem -Force -Path $target
    if ($items.Count -gt 0) {
        Write-Host "La carpeta ya existe y contiene archivos: $target"
        Write-Host "No se sobrescribio automaticamente para proteger trabajo existente."
        exit 1
    }
} else {
    New-Item -ItemType Directory -Force -Path $target | Out-Null
}

Get-ChildItem -Force -Path $source | Where-Object { $_.Name -ne "scripts" } | ForEach-Object {
    Copy-Item -Path $_.FullName -Destination $target -Recurse -Force
}

New-Item -ItemType Directory -Force -Path (Join-Path $target "scripts") | Out-Null
Copy-Item -Path (Join-Path $source "scripts\crear_estructura.ps1") -Destination (Join-Path $target "scripts\crear_estructura.ps1") -Force

Write-Host "Laboratorio TerrarIA creado en $target"
Write-Host "Abre platform\frontend\index.html para ver la landing inicial."
