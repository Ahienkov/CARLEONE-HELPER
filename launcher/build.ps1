$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$compilerPath = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$sourcePath = Join-Path $PSScriptRoot 'Program.cs'
$outputPath = Join-Path $projectRoot 'GTA 5 RP HELPER.exe'
$iconPath = Join-Path $projectRoot 'assets\app-icon.ico'
$manifestPath = Join-Path $PSScriptRoot 'app.manifest'
& $compilerPath /nologo /target:winexe /optimize+ /reference:System.Windows.Forms.dll "/win32icon:$iconPath" "/win32manifest:$manifestPath" "/out:$outputPath" $sourcePath
if ($LASTEXITCODE -ne 0) {
    throw 'Не удалось собрать GTA 5 RP HELPER.exe'
}
Write-Output "Готово: $outputPath"
