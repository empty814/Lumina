"""
lumina/digest/collectors — 各数据源采集函数包

子模块：
  system.py  — 终端历史、Git 提交、剪贴板
  apps.py    — 浏览器历史、备忘录、日历、AI 对话
  files.py   — 本地 Markdown 笔记
"""
from .apps import (
    collect_ai_queries,
    collect_browser_history,
    collect_calendar,
    collect_notes_app,
)
from .files import _last_md_files, collect_markdown_notes
from .system import collect_clipboard, collect_git_logs, collect_shell_history

COLLECTORS = [
    collect_shell_history,
    collect_git_logs,
    collect_clipboard,
    collect_browser_history,
    collect_calendar,
    collect_notes_app,
    collect_markdown_notes,
    collect_ai_queries,
]

__all__ = [
    "collect_shell_history",
    "collect_git_logs",
    "collect_clipboard",
    "collect_browser_history",
    "collect_notes_app",
    "collect_calendar",
    "collect_markdown_notes",
    "collect_ai_queries",
    "_last_md_files",
    "COLLECTORS",
]
