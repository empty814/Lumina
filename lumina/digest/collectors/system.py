"""
lumina/digest/collectors/system.py — 系统级数据源采集

包含：终端历史、Git 提交、剪贴板、以及辅助的 git 目录遍历函数。
"""
import logging
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from lumina.digest.config import get_cfg

logger = logging.getLogger("lumina.digest")

_GIT_SKIP_DIRS = {".git", ".venv", "node_modules", "build", "dist", "__pycache__", ".app"}


def _walk_git_dirs(root: Path, max_depth: int = 4):
    """yield 深度 ≤ max_depth 的 .git 目录父路径（即仓库根），不进入忽略目录。"""
    def _recurse(path: Path, depth: int):
        if depth > max_depth:
            return
        try:
            with os.scandir(path) as it:
                entries = list(it)
        except (PermissionError, OSError):
            return
        for entry in entries:
            if entry.name == ".git" and entry.is_dir(follow_symlinks=False):
                yield Path(entry.path)
            elif entry.is_dir(follow_symlinks=False) and entry.name not in _GIT_SKIP_DIRS:
                yield from _recurse(Path(entry.path), depth + 1)
    yield from _recurse(root, 0)


def collect_shell_history(n: int = 100) -> str:
    cfg = get_cfg()
    cutoff = time.time() - cfg.history_hours * 3600
    try:
        zsh  = Path.home() / ".zsh_history"
        bash = Path.home() / ".bash_history"
        src  = zsh if zsh.exists() else (bash if bash.exists() else None)
        if not src:
            return ""
        raw = src.read_text(errors="replace").splitlines()

        cmds: list[str] = []
        seen: set[str] = set()
        has_timestamps = False

        for line in reversed(raw):
            ts_val: Optional[float] = None
            cmd = line

            # 解析 zsh 扩展格式：": <unix_ts>:<elapsed>;<command>"
            if line.startswith(": ") and ";" in line:
                try:
                    meta, cmd = line.split(";", 1)
                    # meta = ": 1712500000:0"  →  parts[1] 是时间戳
                    ts_str = meta.split(":")[1].strip()
                    ts_val = float(ts_str)
                    has_timestamps = True
                except (ValueError, IndexError):
                    pass

            if ts_val is not None:
                # 倒序迭代：遇到早于 cutoff 的记录即可停止
                if ts_val <= cutoff:
                    break

            cmd = cmd.strip()
            if not cmd or cmd in seen:
                continue
            seen.add(cmd)
            cmds.append(cmd)
            if len(cmds) >= n:
                break

        # 兜底：整个文件无可解析时间戳（bash history 或纯文本格式）
        # → 回退到原来的取最近 n 条逻辑
        if not has_timestamps:
            cmds, seen = [], set()
            for line in reversed(raw):
                if line.startswith(": ") and ";" in line:
                    line = line.split(";", 1)[1]
                line = line.strip()
                # 跳过 bash HISTTIMEFORMAT 产生的 "#<unix_ts>" 行
                if line.startswith("#") and line[1:].isdigit():
                    continue
                if not line or line in seen:
                    continue
                seen.add(line)
                cmds.append(line)
                if len(cmds) >= n:
                    break

        if not cmds:
            return ""
        return "## 终端历史（最近命令）\n" + "\n".join(f"  {c}" for c in reversed(cmds))
    except Exception as e:
        logger.debug("shell history: %s", e)
        return ""


def collect_git_logs(n: int = 20) -> str:
    cfg = get_cfg()
    cutoff = time.time() - cfg.history_hours * 3600
    since = datetime.fromtimestamp(cutoff).strftime("%Y-%m-%d %H:%M")
    try:
        entries, seen_repos = [], set()

        for root_str in cfg.scan_dirs:
            root = Path(root_str).expanduser()
            if not root.exists():
                continue
            for git_dir in _walk_git_dirs(root, max_depth=4):
                repo_dir = git_dir.parent
                if repo_dir in seen_repos:
                    continue
                seen_repos.add(repo_dir)
                try:
                    # "%ct %H %s"：commit Unix 时间戳 + hash + subject
                    result = subprocess.run(
                        ["git", "log", "--format=%ct %H %s",
                         f"--since={since}", f"-{n}"],
                        cwd=str(repo_dir), capture_output=True, text=True, timeout=5
                    )
                    lines = result.stdout.strip().splitlines()
                    if lines:
                        display_lines = []
                        for raw_line in lines:
                            parts = raw_line.split(" ", 2)
                            if len(parts) == 3:
                                _, hash_part, subject = parts
                                display_lines.append(f"  {hash_part[:7]} {subject}")
                            else:
                                display_lines.append(f"  {raw_line}")
                        entries.append(f"**{repo_dir.name}**:\n" +
                                       "\n".join(display_lines))
                except Exception:
                    continue

        if not entries:
            return ""
        return "## Git 提交（过去 %.0fh）\n" % cfg.history_hours + "\n\n".join(entries)
    except Exception as e:
        logger.debug("git logs: %s", e)
        return ""


def collect_clipboard() -> str:
    # 无状态，不使用 cutoff
    try:
        from lumina.platform_utils import clipboard_get
        content = clipboard_get().strip()
        if not content:
            return ""
        if len(content) > 500:
            content = content[:500] + "…（已截断）"
        return f"## 剪贴板内容\n{content}"
    except Exception as e:
        logger.debug("clipboard: %s", e)
        return ""
