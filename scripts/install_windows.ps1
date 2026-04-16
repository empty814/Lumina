Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir

Write-Host "=== 安装 Lumina (Windows) ==="
Write-Host "项目目录: $ProjectDir"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "未检测到 uv，开始安装..."
    irm https://astral.sh/uv/install.ps1 | iex
    $env:Path += ";$HOME\.local\bin"
}

Set-Location $ProjectDir
uv sync

Write-Host ""
Write-Host "✓ 依赖安装完成"
Write-Host "启动服务："
Write-Host "  uv run lumina server"
Write-Host ""
Write-Host "运行 smoke 检查："
Write-Host "  uv run python scripts/smoke_check.py"
