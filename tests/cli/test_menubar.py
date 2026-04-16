from __future__ import annotations

import json
import sys
from types import SimpleNamespace

from lumina.config import get_config, reset_config


def test_config_reads_desktop_menubar_flag(tmp_path):
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(
        json.dumps(
            {
                "provider": {"type": "local", "model_path": None, "openai": {}},
                "host": "127.0.0.1",
                "port": 19999,
                "log_level": "INFO",
                "digest": {},
                "desktop": {"menubar_enabled": False},
                "system_prompts": {},
            }
        ),
        encoding="utf-8",
    )

    reset_config()
    try:
        cfg = get_config(str(cfg_file))
        assert cfg.desktop.menubar_enabled is False
    finally:
        reset_config()


def test_persist_menubar_enabled_writes_user_config(tmp_path, monkeypatch):
    import lumina.config_runtime as config_runtime

    user_cfg = tmp_path / "user-config.json"
    source_cfg = tmp_path / "source-config.json"
    source_cfg.write_text(json.dumps({"host": "127.0.0.1"}), encoding="utf-8")
    monkeypatch.setattr(config_runtime, "USER_CONFIG_PATH", user_cfg)

    import lumina.cli.utils as cli_utils
    cli_utils.persist_menubar_enabled(False, config_path=str(source_cfg))

    data = json.loads(source_cfg.read_text(encoding="utf-8"))
    assert data["desktop"]["menubar_enabled"] is False


def test_resolve_menubar_enabled_prefers_cli_override():
    from lumina.cli.server import _resolve_menubar_enabled

    cfg = SimpleNamespace(desktop=SimpleNamespace(menubar_enabled=False))

    assert _resolve_menubar_enabled(cfg, SimpleNamespace(menubar=None)) is False
    assert _resolve_menubar_enabled(cfg, SimpleNamespace(menubar=True)) is True
    assert _resolve_menubar_enabled(cfg, SimpleNamespace(menubar=False)) is False


def test_cmd_menubar_restarts_running_service(monkeypatch):
    import lumina.cli.server as server

    killed = []
    removed = []
    persisted = []
    launched = []

    monkeypatch.setattr(server.os, "kill", lambda pid, sig: killed.append((pid, sig)))
    monkeypatch.setattr(sys, "argv", ["lumina", "menubar", "off"])

    monkeypatch.setattr(
        "lumina.cli.utils.read_pid",
        lambda: 4321,
    )
    monkeypatch.setattr(
        "lumina.cli.utils.remove_pid",
        lambda: removed.append(True),
    )
    monkeypatch.setattr(
        "lumina.cli.utils.resolve_config_path",
        lambda: "/tmp/lumina-config.json",
    )
    monkeypatch.setattr(
        "lumina.cli.utils.persist_menubar_enabled",
        lambda enabled, config_path=None: persisted.append((enabled, config_path)),
    )

    monkeypatch.setattr("subprocess.Popen", lambda cmd: launched.append(cmd))

    server.cmd_menubar(SimpleNamespace(state="off"))

    assert persisted == [(False, "/tmp/lumina-config.json")]
    assert killed and killed[0][0] == 4321
    assert removed == [True]
    assert launched == [["lumina", "server", "--no-menubar"]]
