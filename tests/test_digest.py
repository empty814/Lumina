"""
Digest 模块单元测试：config、cursor_store、collectors 的核心逻辑。
不依赖真实 LLM，不触发真实采集（对系统文件只做 mock）。
"""
import json
import os
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest


# ── DigestConfig ─────────────────────────────────────────────────────────────

def test_digest_config_defaults():
    from lumina.digest.config import DigestConfig
    cfg = DigestConfig()
    assert cfg.history_hours == 24.0
    assert cfg.refresh_hours == 1.0
    assert cfg.notify_time == "20:00"
    assert cfg.enabled_collectors is None
    assert cfg.enabled is False  # 默认关闭，需显式启用


def test_digest_config_configure():
    from lumina.digest.config import configure, get_cfg
    configure({"digest": {
        "enabled": False,
        "history_hours": 12,
        "refresh_hours": 0.5,
        "notify_time": "09:00",
        "enabled_collectors": ["collect_shell_history", "collect_git_logs"],
    }})
    cfg = get_cfg()
    assert cfg.history_hours == 12.0
    assert cfg.refresh_hours == 0.5
    assert cfg.notify_time == "09:00"
    assert cfg.enabled_collectors == ["collect_shell_history", "collect_git_logs"]
    assert cfg.enabled is False


def test_digest_config_enabled_collectors_null():
    from lumina.digest.config import configure, get_cfg
    configure({"digest": {"enabled_collectors": None}})
    assert get_cfg().enabled_collectors is None


def test_digest_config_scan_dirs_empty_means_no_scan():
    # scan_dirs=[] 的语义是"不扫描任何目录"，而非回退到默认值
    from lumina.digest.config import configure, get_cfg
    configure({"digest": {"scan_dirs": []}})
    assert get_cfg().scan_dirs == []


def test_digest_config_scan_dirs_missing_uses_defaults():
    # 配置中没有 scan_dirs key 时，才回退到默认目录列表
    from lumina.digest.config import configure, get_cfg, DigestConfig
    configure({"digest": {}})
    assert get_cfg().scan_dirs == DigestConfig().scan_dirs


# ── md5_of_file ───────────────────────────────────────────────────────────────

def test_md5_of_file(tmp_path):
    from lumina.digest.cursor_store import md5_of_file
    f = tmp_path / "note.md"
    f.write_text("hello world")
    h1 = md5_of_file(f)
    assert len(h1) == 32
    # 内容不变，hash 不变
    assert md5_of_file(f) == h1
    # 内容改变，hash 改变
    f.write_text("hello world!")
    assert md5_of_file(f) != h1


def test_md5_of_file_missing_returns_stable_value(tmp_path):
    """文件不存在时，md5_of_file 返回固定值（空内容的 md5），不抛异常。"""
    from lumina.digest.cursor_store import md5_of_file
    result = md5_of_file(tmp_path / "ghost.md")
    # 返回值稳定（不随调用变化），且与有内容的文件不同
    assert result == md5_of_file(tmp_path / "ghost.md")
    real = tmp_path / "real.md"
    real.write_text("content")
    assert result != md5_of_file(real)


# ── md_hashes roundtrip ────────────────────────────────────────────────────────

def test_md_hashes_roundtrip(tmp_path):
    from lumina.digest import cursor_store
    original_path = cursor_store.MD_HASHES_PATH
    cursor_store.MD_HASHES_PATH = tmp_path / "md_hashes.json"
    try:
        data = {"/some/file.md": "abc123", "/other/note.md": "def456"}
        cursor_store.save_md_hashes(data)
        loaded = cursor_store.load_md_hashes()
        assert loaded == data
    finally:
        cursor_store.MD_HASHES_PATH = original_path


def test_md_hashes_missing_file_returns_empty(tmp_path):
    from lumina.digest import cursor_store
    original_path = cursor_store.MD_HASHES_PATH
    cursor_store.MD_HASHES_PATH = tmp_path / "nonexistent.json"
    try:
        assert cursor_store.load_md_hashes() == {}
    finally:
        cursor_store.MD_HASHES_PATH = original_path


# ── enabled_collectors 过滤 ────────────────────────────────────────────────────

def test_enabled_collectors_filters_active():
    """_collect_all 应只运行 enabled_collectors 里的 collector。"""
    from lumina.digest.config import configure
    configure({"digest": {"enabled_collectors": ["collect_shell_history"]}})

    called = []

    def collect_shell_history():  # 函数名必须与 enabled_collectors 条目一致
        called.append("collect_shell_history")
        return ""

    def collect_git_logs():
        called.append("collect_git_logs")
        return ""

    import lumina.digest.core as core
    original = core._COLLECTORS[:]
    core._COLLECTORS = [collect_shell_history, collect_git_logs]

    try:
        import asyncio
        asyncio.run(core._collect_all())
        assert called == ["collect_shell_history"]  # git_logs 被过滤掉
    finally:
        core._COLLECTORS = original
        configure({"digest": {}})


# ── config reset_config ────────────────────────────────────────────────────────

def test_reset_config(tmp_path):
    from lumina.config import get_config, reset_config

    # 写一个临时 config
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(json.dumps({
        "provider": {"type": "local", "model_path": None, "openai": {}},
        "host": "127.0.0.1",
        "port": 19999,
        "log_level": "INFO",
        "digest": {},
        "system_prompts": {},
    }))

    reset_config()
    cfg = get_config(str(cfg_file))
    assert cfg.port == 19999

    reset_config()
    cfg2 = get_config(str(cfg_file))
    assert cfg2.port == 19999

    reset_config()  # 清理，不污染其他测试


def test_config_defaults_model_path_to_user_cache_dir(tmp_path):
    from lumina.config import get_config, reset_config

    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(
        json.dumps(
            {
                "provider": {"type": "local", "model_path": None, "openai": {}},
                "host": "127.0.0.1",
                "port": 19999,
                "log_level": "INFO",
                "digest": {},
                "system_prompts": {},
            }
        )
    )

    reset_config()
    cfg = get_config(str(cfg_file))
    assert cfg.provider.model_path == str(
        Path.home() / ".lumina" / "models" / "qwen3.5-0.8b-4bit"
    )
    reset_config()


def test_config_respects_ptt_enabled_flag(tmp_path):
    from lumina.config import get_config, reset_config

    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(
        json.dumps(
            {
                "provider": {"type": "local", "model_path": None, "openai": {}},
                "host": "127.0.0.1",
                "port": 19999,
                "log_level": "INFO",
                "digest": {},
                "ptt": {"enabled": False, "hotkey": "f5", "language": "zh"},
                "system_prompts": {},
            }
        )
    )

    reset_config()
    cfg = get_config(str(cfg_file))
    assert cfg.ptt.enabled is False
    reset_config()


def test_config_ptt_enabled_defaults_to_false_when_missing(tmp_path):
    from lumina.config import get_config, reset_config

    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(
        json.dumps(
            {
                "provider": {"type": "local", "model_path": None, "openai": {}},
                "host": "127.0.0.1",
                "port": 19999,
                "log_level": "INFO",
                "digest": {},
                "ptt": {"hotkey": "f5", "language": "zh"},
                "system_prompts": {},
            }
        )
    )

    reset_config()
    cfg = get_config(str(cfg_file))
    assert cfg.ptt.enabled is False
    reset_config()


def test_get_status_recovers_generated_at_from_existing_digest(tmp_path):
    import lumina.digest.core as core

    digest_path = tmp_path / "digest.md"
    digest_path.write_text("# existing digest\n", encoding="utf-8")
    mtime = time.time() - 123
    os.utime(digest_path, (mtime, mtime))

    with patch.object(core, "_DIGEST_PATH", digest_path), \
         patch.object(core, "_generated_at", None), \
         patch.object(core, "_last_generated_ts", None):
        status = core.get_status()

    assert status["generating"] is False
    assert status["generated_at"] == datetime.fromtimestamp(mtime).isoformat()


@pytest.mark.asyncio
async def test_maybe_generate_digest_skips_when_lock_held(tmp_path):
    """asyncio.Lock 持有期间，并发的 maybe_generate_digest 调用应该直接跳过，不重入。"""
    import asyncio
    import lumina.digest.core as core
    from lumina.digest.config import configure

    configure({"digest": {"enabled": True}})

    digest_path = tmp_path / "digest.md"
    generate_calls = 0
    shared_lock = asyncio.Lock()

    async def _slow_generate(llm):
        nonlocal generate_calls
        generate_calls += 1
        await asyncio.sleep(0.05)

    with patch.object(core, "_DIGEST_PATH", digest_path), \
         patch.object(core, "_generated_at", None), \
         patch.object(core, "_last_generated_ts", None), \
         patch.object(core, "generate_digest", _slow_generate), \
         patch.object(core, "_collect_all", AsyncMock(return_value="mocked context")):
        # 注入共享 lock，使两次并发调用看到同一个实例
        core._digest_lock = shared_lock
        try:
            await asyncio.gather(
                core.maybe_generate_digest(object(), force_full=True),
                core.maybe_generate_digest(object(), force_full=True),
            )
        finally:
            core._digest_lock = None

    assert generate_calls == 1, f"Expected 1 generate call, got {generate_calls}"


@pytest.mark.asyncio
async def test_maybe_generate_digest_skips_when_disabled():
    import lumina.digest.core as core
    from lumina.digest.config import configure

    class FakeLLM:
        generate = AsyncMock(return_value="digest body")

    configure({"digest": {"enabled": False}})
    try:
        with patch.object(core, "generate_digest", AsyncMock()) as mocked_generate:
            await core.maybe_generate_digest(FakeLLM(), force_full=True)
        mocked_generate.assert_not_called()
    finally:
        configure({"digest": {"enabled": True}})
