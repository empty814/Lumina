#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== 安装 Lumina (Linux) ==="
echo "项目目录: $PROJECT_DIR"

if ! command -v uv >/dev/null 2>&1; then
    echo "未检测到 uv，开始安装..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

cd "$PROJECT_DIR"
uv sync

echo
echo "✓ 依赖安装完成"
echo "启动服务："
echo "  uv run lumina server"
echo
echo "运行 smoke 检查："
echo "  uv run python scripts/smoke_check.py"
