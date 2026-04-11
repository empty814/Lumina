"""
lumina/cli/utils.py — 启动共用工具函数

包含：日志配置、配置路径解析、config 深度合并同步、
持久化写入、PID 管理、系统通知、端口检测、就绪横幅等。
"""
import json
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger("lumina")

# 打包时注入的版本标记
_EDITION = os.environ.get("LUMINA_EDITION")

# 用户级配置文件路径
_USER_CONFIG_PATH = Path.home() / ".lumina" / "config.json"

# PID 文件
_PID_FILE = Path.home() / ".lumina" / "lumina.pid"


# ── 日志 ──────────────────────────────────────────────────────────────────────

def setup_logging(level: str = "INFO"):
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s  %(levelname)-8s  %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def uvicorn_log_config(level: str = "INFO") -> dict:
    """返回带时间戳的 uvicorn 日志配置。"""
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "()": "uvicorn.logging.DefaultFormatter",
                "fmt": "%(asctime)s  %(levelprefix)s %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
                "use_colors": None,
            },
            "access": {
                "()": "uvicorn.logging.AccessFormatter",
                "fmt": '%(asctime)s  %(levelprefix)s %(client_addr)s  "%(request_line)s"  %(status_code)s',
                "datefmt": "%Y-%m-%d %H:%M:%S",
                "use_colors": None,
            },
        },
        "handlers": {
            "default": {"class": "logging.StreamHandler", "formatter": "default", "stream": "ext://sys.stderr"},
            "access":  {"class": "logging.StreamHandler", "formatter": "access",  "stream": "ext://sys.stdout"},
        },
        "loggers": {
            "uvicorn":        {"handlers": ["default"], "level": level.upper(), "propagate": False},
            "uvicorn.error":  {"handlers": ["default"], "level": level.upper(), "propagate": False},
            "uvicorn.access": {"handlers": ["access"],  "level": "INFO",        "propagate": False},
        },
    }


# ── Config 工具 ───────────────────────────────────────────────────────────────

def deep_merge(base: dict, override: dict) -> dict:
    """
    深度合并：以 base 为模板，override 里有的 key 优先保留，
    base 里有但 override 里没有的 key 补入。
    不修改入参，返回新 dict。
    """
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def _flatten_keys(d: dict, prefix: str = "") -> set:
    """递归收集所有叶节点路径，用于 diff 日志。"""
    keys = set()
    for k, v in d.items():
        full = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            keys |= _flatten_keys(v, full)
        else:
            keys.add(full)
    return keys


def sync_user_config() -> None:
    """
    启动时将项目模板 config.json 里新增的字段补入用户配置，
    用户已有的值一律不覆盖。
    """
    if not _USER_CONFIG_PATH.exists():
        return

    pkg_cfg_path = Path(__file__).parent.parent / "config.json"
    if not pkg_cfg_path.exists():
        return

    try:
        with open(pkg_cfg_path, "r", encoding="utf-8") as f:
            template = json.load(f)
        with open(_USER_CONFIG_PATH, "r", encoding="utf-8") as f:
            user = json.load(f)
    except Exception as e:
        logger.warning("Config sync: failed to read config files: %s", e)
        return

    merged = deep_merge(template, user)
    if merged == user:
        return

    try:
        with open(_USER_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=2, ensure_ascii=False)
        new_keys = [k for k in _flatten_keys(merged) if k not in _flatten_keys(user)]
        logger.info("Config sync: added %d new key(s): %s", len(new_keys), new_keys)
    except Exception as e:
        logger.warning("Config sync: failed to write user config: %s", e)


def resolve_config_path() -> str | None:
    """
    确定加载哪个 config.json：
      1. 用户级配置（~/.lumina/config.json）优先
      2. 返回 None，由 get_config() 用默认路径
    """
    if _USER_CONFIG_PATH.exists():
        return str(_USER_CONFIG_PATH)
    return None


# ── 持久化写入 ────────────────────────────────────────────────────────────────

def _read_or_init_config(config_path: str | None) -> dict:
    target = _USER_CONFIG_PATH
    source = Path(config_path) if config_path else (Path(__file__).parent.parent / "config.json")
    if target.exists():
        with open(target, "r", encoding="utf-8") as f:
            return json.load(f)
    if source.exists():
        with open(source, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _write_user_config(data: dict) -> None:
    _USER_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_USER_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def persist_ptt_enabled(enabled: bool, config_path: str | None = None) -> None:
    data = _read_or_init_config(config_path)
    ptt_cfg = data.get("ptt")
    if not isinstance(ptt_cfg, dict):
        ptt_cfg = {}
    ptt_cfg["enabled"] = bool(enabled)
    data["ptt"] = ptt_cfg
    _write_user_config(data)


def persist_host(host: str, config_path: str | None = None) -> None:
    data = _read_or_init_config(config_path)
    data["host"] = host
    _write_user_config(data)


def persist_digest_enabled(enabled: bool, config_path: str | None = None) -> None:
    data = _read_or_init_config(config_path)
    digest_cfg = data.get("digest")
    if not isinstance(digest_cfg, dict):
        digest_cfg = {}
    digest_cfg["enabled"] = bool(enabled)
    data["digest"] = digest_cfg
    _write_user_config(data)


# ── PID 管理 ──────────────────────────────────────────────────────────────────

def write_pid():
    _PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    _PID_FILE.write_text(str(os.getpid()))


def read_pid() -> int | None:
    try:
        return int(_PID_FILE.read_text().strip())
    except Exception:
        return None


def remove_pid():
    _PID_FILE.unlink(missing_ok=True)


# ── 系统工具 ──────────────────────────────────────────────────────────────────

def notify(title: str, message: str):
    """发送系统通知（macOS App 打包模式）；其他平台/模式静默。"""
    if sys.platform != "darwin" or _EDITION not in ("full", "lite"):
        return
    import subprocess
    script = (
        f'display notification "{message}" '
        f'with title "{title}" '
        f'sound name "default"'
    )
    try:
        subprocess.Popen(["osascript", "-e", script],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        logger.debug("Notification failed: %s", e)


def is_port_in_use(host: str, port: int) -> bool:
    import socket
    check_host = "127.0.0.1" if host in ("0.0.0.0", "") else host
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((check_host, port)) == 0


def get_lan_ip() -> str | None:
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return None


def print_ready_banner(host: str, port: int):
    edition_label = {"full": "Full", "lite": "Lite"}.get(_EDITION, "Dev")
    print()
    print("=" * 55)
    print(f"  Lumina {edition_label} 已就绪")
    print(f"  本机访问：http://127.0.0.1:{port}")

    if host in ("0.0.0.0", ""):
        lan_ip = get_lan_ip()
        if lan_ip:
            print(f"  局域网访问：http://{lan_ip}:{port}")
            print("  手机扫码或在 Safari 打开上方地址")
            print("  添加到主屏幕即可像 App 一样使用")

    print("=" * 55)
    print()

    notify("Lumina 已就绪", f"服务运行于 http://127.0.0.1:{port}")


def is_digest_enabled() -> bool:
    from lumina.digest.config import get_cfg
    return bool(get_cfg().enabled)
