Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$SendToDir = Join-Path $env:APPDATA "Microsoft\Windows\SendTo"

New-Item -ItemType Directory -Force -Path $SendToDir | Out-Null

function Write-SendToFile {
    param(
        [string]$Name,
        [string]$Action
    )

    $Path = Join-Path $SendToDir $Name
    $Content = @"
@echo off
cd /d "$ProjectDir"
uv run python "$ProjectDir\scripts\lumina_file_action.py" $Action %*
pause
"@
    Set-Content -Path $Path -Value $Content -Encoding ASCII
}

Write-SendToFile -Name "Lumina Translate PDF.cmd" -Action "translate"
Write-SendToFile -Name "Lumina Summarize PDF.cmd" -Action "summarize"
Write-SendToFile -Name "Lumina Polish Text.cmd" -Action "polish"

Write-Host "Installed SendTo integrations:"
Write-Host "  Lumina Translate PDF.cmd"
Write-Host "  Lumina Summarize PDF.cmd"
Write-Host "  Lumina Polish Text.cmd"
Write-Host ""
Write-Host "You can now right-click files and use Send to -> Lumina ..."
