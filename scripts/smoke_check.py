#!/usr/bin/env python3
"""
跨平台 smoke 检查入口。

用于本地快速确认：
1. 关键平台抽象测试通过
2. 服务/API/digest 基本契约未被破坏
3. 最近新增的核心文件满足 ruff
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent.parent

TEST_TARGETS = [
    "tests/test_server_api.py",
    "tests/test_digest.py",
    "tests/unit/test_config.py",
    "tests/unit/test_config_router.py",
    "tests/unit/test_platform_support.py",
    "tests/unit/test_popup.py",
    "tests/unit/test_provider_resolution.py",
    "tests/unit/test_lumina_file_action.py",
]

RUFF_TARGETS = [
    "lumina/platform_support",
    "lumina/config.py",
    "lumina/platform_utils.py",
    "lumina/cli/server.py",
    "lumina/cli/setup.py",
    "lumina/cli/utils.py",
    "lumina/asr/transcriber.py",
    "lumina/digest/collectors/apps.py",
    "lumina/digest/collectors/system.py",
    "lumina/popup.py",
    "scripts/lumina_file_action.py",
]


def _run(cmd: list[str]) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, cwd=PROJECT_DIR, check=True)


def main() -> int:
    try:
        _run(["uv", "run", "pytest", "-q", *TEST_TARGETS])
        _run(["uv", "run", "ruff", "check", *RUFF_TARGETS])
    except subprocess.CalledProcessError as exc:
        return exc.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
