"""
lumina/digest/collectors/files.py — 本地文件数据源采集

包含：Markdown 笔记扫描，以及辅助的 md 文件遍历函数。
"""
import logging
import os
import time
from pathlib import Path

from lumina.digest.config import get_cfg
from lumina.digest.cursor_store import load_md_hashes, md5_of_file, save_md_hashes

logger = logging.getLogger("lumina.digest")

_MD_SKIP_PARTS = {".app", "build", "dist", "node_modules", ".git", ".venv", "__pycache__"}

# 上次 collect_markdown_notes 扫到的文件列表，供 debug 面板展示
_last_md_files: list[dict] = []


def _walk_md_files(root: Path, max_depth: int = 4):
    """yield 深度 ≤ max_depth 的 .md 文件，不进入忽略目录及隐藏目录。"""
    root_str = str(root)
    root_depth = root_str.count(os.sep)
    for dirpath, dirnames, filenames in os.walk(root_str):
        cur_depth = dirpath.count(os.sep) - root_depth
        if cur_depth >= max_depth:
            dirnames.clear()
        else:
            dirnames[:] = [
                d for d in dirnames
                if d not in _MD_SKIP_PARTS and not d.startswith(".")
            ]
        for fname in filenames:
            if fname.endswith(".md"):
                yield Path(dirpath) / fname


def collect_markdown_notes() -> str:
    """扫描 scan_dirs 下最近修改的 .md 文件。

    两级过滤：
    1. mtime > cutoff（快速跳过明显旧文件）
    2. md5(前4KB) 与上次采集不同（过滤 Cursor/iCloud 等 mtime-only 误触发）
    """
    cfg = get_cfg()
    cutoff = time.time() - cfg.history_hours * 3600
    try:
        hashes = load_md_hashes()
        candidates: list[tuple[float, Path]] = []

        for root_str in cfg.scan_dirs:
            root = Path(root_str).expanduser()
            if not root.exists():
                continue
            for md in _walk_md_files(root, max_depth=4):
                try:
                    mtime = md.stat().st_mtime
                    if mtime <= cutoff:
                        continue
                    # mtime 有变化，再用 md5 确认内容是否真的改了
                    key = str(md)
                    current_hash = md5_of_file(md)
                    if hashes.get(key) == current_hash:
                        # 内容未变（编辑器扫描/同步等误触发），更新 hash 记录但不采集
                        hashes[key] = current_hash
                        continue
                    candidates.append((mtime, md, current_hash))
                except Exception:
                    continue

        global _last_md_files
        _last_md_files = [
            {"path": str(md), "mtime": mtime}
            for mtime, md, _ in sorted(candidates, key=lambda x: -x[0])
        ]

        if not candidates:
            return ""

        candidates.sort(key=lambda x: -x[0])

        entries = []
        succeeded: set = set()
        for mtime, md, current_hash in candidates[:10]:
            try:
                with md.open(errors="replace") as _f:
                    content = _f.read(200).strip()
                if content:
                    entries.append(f"**{md.name}**:\n  {content}")
                    succeeded.add(md)
            except Exception:
                logger.debug("markdown notes: failed to read %s", md)
                continue

        # 只更新成功读出内容的文件 hash，读取失败或超出前 10 名的文件保留旧 hash，
        # 确保下次运行仍可重新采集
        if entries:
            for mtime, md, current_hash in candidates[:10]:
                if md in succeeded:
                    hashes[str(md)] = current_hash
            save_md_hashes(hashes)

        if not entries:
            return ""
        return "## 本地 Markdown 笔记\n" + "\n\n".join(entries)
    except Exception as e:
        logger.debug("markdown notes: %s", e)
        return ""
