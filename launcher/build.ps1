$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$compilerPath = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$sourcePath = Join-Path $PSScriptRoot 'Program.cs'
$outputPath = Join-Path $projectRoot 'CARLEONE HELPER.exe'
$iconPath = Join-Path $projectRoot 'assets\app-icon.ico'
& $compilerPath /nologo /target:winexe /optimize+ /reference:System.Windows.Forms.dll "/win32icon:$iconPath" "/out:$outputPath" $sourcePath
if ($LASTEXITCODE -ne 0) {
    throw 'Не удалось собрать CARLEONE HELPER.exe'
}
Write-Output "Готово: $outputPath"
