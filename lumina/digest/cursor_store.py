"""
lumina/digest/cursor_store.py — Per-collector cursor persistence.

Cursors are Unix timestamps (float seconds since epoch), keyed by collector
function name. Stored in ~/.lumina/collector_cursors.json.

Usage:
    cursors = load_cursors()          # {} on any error
    cursors["collect_git_logs"] = ts
    save_cursors(cursors)             # atomic write, errors are swallowed
"""
import json
import logging
from pathlib import Path
from typing import Dict

logger = logging.getLogger("lumina.digest")

CURSOR_PATH = Path.home() / ".lumina" / "collector_cursors.json"


def load_cursors() -> Dict[str, float]:
    """Load per-collector cursors from disk.

    Returns an empty dict on any read/parse error — all collectors will
    fall back to cfg.history_hours as their initial window.
    """
    try:
        data = json.loads(CURSOR_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            logger.debug("cursor store: unexpected type %s, resetting", type(data))
            return {}
        return {
            k: float(v)
            for k, v in data.items()
            if isinstance(k, str) and isinstance(v, (int, float)) and float(v) > 0
        }
    except FileNotFoundError:
        return {}
    except Exception as e:
        logger.debug("cursor store load error: %s", e)
        return {}


def save_cursors(cursors: Dict[str, float]) -> None:
    """Persist cursors atomically. Errors are logged and swallowed."""
    try:
        CURSOR_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = CURSOR_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(cursors, indent=2, ensure_ascii=False),
                       encoding="utf-8")
        tmp.replace(CURSOR_PATH)
    except Exception as e:
        logger.warning("cursor store save error: %s", e)
