"""
lumina/platform_support/paths.py — 跨平台桌面与采集路径发现。
"""
from __future__ import annotations

from pathlib import Path

from .runtime import IS_MACOS, IS_WINDOWS


def _expand(path: str) -> Path:
    return Path(path).expanduser()


def _glob(pattern: str) -> list[Path]:
    expanded = pattern.replace("~/", "")
    return sorted(Path.home().glob(expanded))


def shell_history_candidates() -> list[Path]:
    candidates = [
        _expand("~/.zsh_history"),
        _expand("~/.bash_history"),
        _expand("~/.local/share/fish/fish_history"),
    ]
    if IS_WINDOWS:
        appdata = Path.home() / "AppData" / "Roaming"
        candidates.append(
            appdata / "Microsoft" / "Windows" / "PowerShell" / "PSReadLine" / "ConsoleHost_history.txt"
        )
    return candidates


def chromium_history_candidates() -> list[Path]:
    patterns: list[str]
    if IS_WINDOWS:
        patterns = [
            "~/AppData/Local/Google/Chrome/User Data/*/History",
            "~/AppData/Local/Microsoft/Edge/User Data/*/History",
            "~/AppData/Local/BraveSoftware/Brave-Browser/User Data/*/History",
        ]
    elif IS_MACOS:
        patterns = [
            "~/Library/Application Support/Google/Chrome/*/History",
            "~/Library/Application Support/Microsoft Edge/*/History",
            "~/Library/Application Support/BraveSoftware/Brave-Browser/*/History",
        ]
    else:
        patterns = [
            "~/.config/google-chrome/*/History",
            "~/.config/chromium/*/History",
            "~/.config/microsoft-edge/*/History",
            "~/.config/BraveSoftware/Brave-Browser/*/History",
            "~/.var/app/com.google.Chrome/config/google-chrome/*/History",
            "~/.var/app/com.brave.Browser/config/BraveSoftware/Brave-Browser/*/History",
        ]

    results: list[Path] = []
    for pattern in patterns:
        results.extend(_glob(pattern))
    return [p for p in results if p.exists()]


def firefox_profile_dirs() -> list[Path]:
    if IS_WINDOWS:
        root = Path.home() / "AppData" / "Roaming" / "Mozilla" / "Firefox" / "Profiles"
    elif IS_MACOS:
        root = Path.home() / "Library" / "Application Support" / "Firefox" / "Profiles"
    else:
        root = Path.home() / ".mozilla" / "firefox"
    if not root.exists():
        return []
    return [p for p in sorted(root.iterdir()) if p.is_dir()]


def safari_history_db() -> Path | None:
    if not IS_MACOS:
        return None
    db = Path.home() / "Library" / "Safari" / "History.db"
    return db if db.exists() else None


def notes_db_path() -> Path | None:
    if not IS_MACOS:
        return None
    db = Path.home() / "Library/Group Containers/group.com.apple.notes/NoteStore.sqlite"
    return db if db.exists() else None


def calendar_db_path() -> Path | None:
    if not IS_MACOS:
        return None
    db = Path.home() / "Library/Group Containers/group.com.apple.calendar/Calendar.sqlitedb"
    return db if db.exists() else None
