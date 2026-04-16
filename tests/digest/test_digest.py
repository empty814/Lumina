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


# ── 平台采集路径适配 ────────────────────────────────────────────────────────────

def test_collect_shell_history_reads_powershell_history(tmp_path):
    from lumina.digest.collectors import system as system_collectors
    from lumina.digest.config import configure

    history = tmp_path / "ConsoleHost_history.txt"
    history.write_text("Get-ChildItem\nSet-Location C:\\work\n", encoding="utf-8")
    configure({"digest": {"history_hours": 24}})

    with patch("lumina.digest.collectors.system.shell_history_candidates", return_value=[history]):
        text = system_collectors.collect_shell_history()

    assert "Get-ChildItem" in text
    assert "Set-Location C:\\work" in text


def test_collect_browser_history_reads_chromium_candidates(tmp_path):
    from lumina.digest.collectors import apps as app_collectors
    from lumina.digest.config import configure

    history_db = tmp_path / "History"
    import sqlite3

    with sqlite3.connect(history_db) as conn:
        conn.execute("CREATE TABLE urls (title TEXT, url TEXT, last_visit_time INTEGER)")
        chrome_offset = 11644473600 * 1_000_000
        now = int(time.time() * 1_000_000 + chrome_offset)
        conn.execute(
            "INSERT INTO urls (title, url, last_visit_time) VALUES (?, ?, ?)",
            ("Edge page", "https://example.com", now),
        )
        conn.commit()

    configure({"digest": {"history_hours": 24}})
    with patch("lumina.digest.collectors.apps.chromium_history_candidates", return_value=[history_db]), \
         patch("lumina.digest.collectors.apps.firefox_profile_dirs", return_value=[]), \
         patch("lumina.digest.collectors.apps.safari_history_db", return_value=None):
        text = app_collectors.collect_browser_history()

    assert "Edge page" in text


def test_collect_ai_queries_reads_cursor_candidates(tmp_path):
    from lumina.digest.collectors import apps as app_collectors
    from lumina.digest.config import configure

    cursor_db = tmp_path / "state.vscdb"
    import sqlite3

    with sqlite3.connect(cursor_db) as conn:
        conn.execute("CREATE TABLE cursorDiskKV (key TEXT, value TEXT)")
        conn.execute(
            "INSERT INTO cursorDiskKV (key, value) VALUES (?, ?)",
            (
                "bubbleId:1",
                json.dumps({"humanChanges": True, "text": "How does the Windows backend work?"}),
            ),
        )
        conn.commit()

    os.utime(cursor_db, None)
    configure({"digest": {"history_hours": 24}})
    with patch("lumina.digest.collectors.apps.cursor_state_db_candidates", return_value=[cursor_db]):
        text = app_collectors.collect_ai_queries()

    assert "Windows backend" in text


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

    # 重置 _state，使 sync_from_digest_file 能从文件恢复 generated_at
    saved_generated_at = core._state.generated_at
    saved_last_ts = core._state.last_generated_ts
    core._state.generated_at = None
    core._state.last_generated_ts = None
    try:
        with patch.object(core, "_DIGEST_PATH", digest_path):
            status = core.get_status()
    finally:
        core._state.generated_at = saved_generated_at
        core._state.last_generated_ts = saved_last_ts

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
         patch.object(core, "generate_digest", _slow_generate), \
         patch.object(core, "_collect_all", AsyncMock(return_value="mocked context")):
        # 注入共享 lock，使两次并发调用看到同一个实例
        saved_lock = core._state._digest_lock
        core._state._digest_lock = shared_lock
        try:
            await asyncio.gather(
                core.maybe_generate_digest(object(), force_full=True),
                core.maybe_generate_digest(object(), force_full=True),
            )
        finally:
            core._state._digest_lock = saved_lock

    assert generate_calls == 1, f"Expected 1 generate call, got {generate_calls}"


# ── DigestState ────────────────────────────────────────────────────────────────

def test_digest_state_thread_safety():
    """多线程并发 set_generating 不应 raise。"""
    import threading
    from lumina.digest.core import DigestState

    state = DigestState()
    errors = []

    def _toggle():
        try:
            for _ in range(200):
                state.set_generating(True)
                state.set_generating(False)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=_toggle) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors


def test_digest_state_set_generated_updates_timestamps():
    from lumina.digest.core import DigestState
    state = DigestState()
    ts = 1_700_000_000.0
    state.set_generated(ts)
    assert state.last_generated_ts == ts
    assert state.generated_at == datetime.fromtimestamp(ts).isoformat()


def test_digest_state_to_status_returns_snapshot():
    from lumina.digest.core import DigestState
    state = DigestState()
    state.set_generating(True)
    status = state.to_status()
    assert status["generating"] is True
    assert "generated_at" in status


# ── CollectorRunner ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_collector_runner_timeout_returns_exception():
    """超时 collector 返回 Exception，不阻塞其他 collector。"""
    from lumina.digest.core import CollectorRunner

    runner = CollectorRunner()

    def _slow():
        import time
        time.sleep(60)  # 远超 TIMEOUT

    def _fast():
        return "fast_result"

    # 临时把 TIMEOUT 改成 0.05s
    orig_timeout = runner.TIMEOUT
    runner.TIMEOUT = 0.05
    try:
        results = await runner.run_all([_slow, _fast], effective_hours=24.0)
    finally:
        runner.TIMEOUT = orig_timeout

    assert isinstance(results["_slow"], Exception)
    assert results["_fast"] == "fast_result"


@pytest.mark.asyncio
async def test_collector_runner_enabled_filter():
    """_collect_all 通过 enabled_collectors 过滤时，CollectorRunner 只运行选中的 collector。"""
    from lumina.digest.core import CollectorRunner

    runner = CollectorRunner()
    called = []

    def collector_a():
        called.append("a")
        return "result_a"

    def collector_b():
        called.append("b")
        return "result_b"

    results = await runner.run_all([collector_a], effective_hours=1.0)
    assert "collector_a" in results
    assert "collector_b" not in results
    assert called == ["a"]


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


def test_collectors_auto_discovered():
    """COLLECTORS 自动发现到所有内置 collect_* 函数。"""
    from lumina.digest.collectors import COLLECTORS

    names = {fn.__name__ for fn in COLLECTORS}
    expected = {
        "collect_shell_history",
        "collect_git_logs",
        "collect_clipboard",
        "collect_browser_history",
        "collect_notes_app",
        "collect_calendar",
        "collect_markdown_notes",
        "collect_ai_queries",
    }
    assert expected.issubset(names)


def test_collector_protocol_satisfied():
    """所有 COLLECTORS 条目满足 Collector Protocol。"""
    from lumina.digest.collectors import COLLECTORS
    from lumina.digest.collectors.base import Collector

    for fn in COLLECTORS:
        assert isinstance(fn, Collector), f"{fn.__name__} does not satisfy Collector protocol"


def test_find_missing_daily_report_keys_uses_snapshot_gaps(tmp_path, monkeypatch):
    import lumina.digest.reports as reports

    monkeypatch.setattr(reports, "DIGEST_SNAPSHOTS_DIR", tmp_path / "snapshots")
    monkeypatch.setattr(reports, "REPORTS_DAILY_DIR", tmp_path / "reports" / "daily")
    monkeypatch.setattr(reports, "REPORTS_WEEKLY_DIR", tmp_path / "reports" / "weekly")
    monkeypatch.setattr(reports, "REPORTS_MONTHLY_DIR", tmp_path / "reports" / "monthly")

    reports.save_snapshot("snapshot-1", datetime(2026, 4, 10, 9, 0))
    reports.save_snapshot("snapshot-2", datetime(2026, 4, 11, 10, 0))
    reports.save_snapshot("snapshot-3", datetime(2026, 4, 12, 11, 0))
    reports.save_report("daily", "2026-04-10", "done")

    missing_before_notify = reports.find_missing_daily_report_keys(
        now=datetime(2026, 4, 12, 19, 0),
        notify_time="20:00",
    )
    missing_after_notify = reports.find_missing_daily_report_keys(
        now=datetime(2026, 4, 12, 21, 0),
        notify_time="20:00",
    )

    assert missing_before_notify == ["2026-04-11"]
    assert missing_after_notify == ["2026-04-11", "2026-04-12"]


def test_find_missing_weekly_and_monthly_report_keys_skip_current_period(tmp_path, monkeypatch):
    import lumina.digest.reports as reports

    monkeypatch.setattr(reports, "DIGEST_SNAPSHOTS_DIR", tmp_path / "snapshots")
    monkeypatch.setattr(reports, "REPORTS_DAILY_DIR", tmp_path / "reports" / "daily")
    monkeypatch.setattr(reports, "REPORTS_WEEKLY_DIR", tmp_path / "reports" / "weekly")
    monkeypatch.setattr(reports, "REPORTS_MONTHLY_DIR", tmp_path / "reports" / "monthly")

    reports.save_report("daily", "2026-03-30", "daily-1")
    reports.save_report("daily", "2026-04-08", "daily-2")
    reports.save_report("daily", "2026-05-06", "daily-3")
    reports.save_report("weekly", reports.weekly_key(datetime(2026, 3, 30).date()), "weekly-1")
    reports.save_report("monthly", "2026-03", "monthly-1")

    missing_weekly = reports.find_missing_weekly_report_keys(today=datetime(2026, 5, 10).date())
    missing_monthly = reports.find_missing_monthly_report_keys(today=datetime(2026, 5, 10).date())

    assert missing_weekly == [reports.weekly_key(datetime(2026, 4, 8).date())]
    assert missing_monthly == ["2026-04"]


@pytest.mark.asyncio
async def test_startup_backfill_reports_fills_historical_gaps(tmp_path, monkeypatch):
    import lumina.cli.server as server
    import lumina.cli.utils as cli_utils
    import lumina.digest as digest
    import lumina.digest.reports as reports
    from lumina.digest.config import configure

    monkeypatch.setattr(reports, "DIGEST_SNAPSHOTS_DIR", tmp_path / "snapshots")
    monkeypatch.setattr(reports, "REPORTS_DAILY_DIR", tmp_path / "reports" / "daily")
    monkeypatch.setattr(reports, "REPORTS_WEEKLY_DIR", tmp_path / "reports" / "weekly")
    monkeypatch.setattr(reports, "REPORTS_MONTHLY_DIR", tmp_path / "reports" / "monthly")

    reports.save_snapshot("snapshot-1", datetime(2026, 4, 1, 9, 0))
    reports.save_snapshot("snapshot-2", datetime(2026, 4, 8, 9, 0))

    calls = []

    async def fake_generate_report(_llm, report_type, key):
        calls.append((report_type, key))
        reports.save_report(report_type, key, f"{report_type}:{key}")
        return f"{report_type}:{key}"

    configure({"digest": {"enabled": True, "notify_time": "20:00"}})
    monkeypatch.setattr(cli_utils, "is_digest_enabled", lambda: True)
    monkeypatch.setattr(digest, "generate_report", fake_generate_report)

    try:
        await server._maybe_backfill_reports(object(), now=datetime(2026, 5, 10, 21, 0))
    finally:
        configure({"digest": {}})

    assert calls == [
        ("daily", "2026-04-01"),
        ("daily", "2026-04-08"),
        ("weekly", reports.weekly_key(datetime(2026, 4, 1).date())),
        ("weekly", reports.weekly_key(datetime(2026, 4, 8).date())),
        ("monthly", "2026-04"),
    ]


def test_digest_scheduler_reload_cancels_and_reschedules(monkeypatch):
    from lumina.digest.config import configure
    from lumina.digest.scheduler import DigestScheduler

    created_timers = []
    startup_calls = []

    class FakeTimer:
        def __init__(self, delay, callback):
            self.delay = delay
            self.callback = callback
            self.cancelled = False
            self.started = False
            created_timers.append(self)

        def start(self):
            self.started = True

        def cancel(self):
            self.cancelled = True

    monkeypatch.setattr("lumina.digest.scheduler.threading.Timer", FakeTimer)
    monkeypatch.setattr(DigestScheduler, "_seconds_to_next_notify", staticmethod(lambda _notify_time: 45))

    configure({"digest": {"enabled": True, "notify_time": "20:00", "refresh_hours": 1}})
    scheduler = DigestScheduler(
        llm=object(),
        get_loop=lambda: None,
        digest_interval_override=30,
    )
    monkeypatch.setattr(scheduler, "_start_startup_digest_thread", lambda: startup_calls.append("startup"))

    try:
        scheduler.start()
        assert [timer.delay for timer in created_timers[:2]] == [30, 45]
        assert all(timer.started for timer in created_timers[:2])
        assert startup_calls == ["startup"]

        scheduler.reload(run_startup=True)
        assert created_timers[0].cancelled is True
        assert created_timers[1].cancelled is True
        assert [timer.delay for timer in created_timers[2:4]] == [30, 45]
        assert startup_calls == ["startup", "startup"]

        scheduler.stop()
        assert created_timers[2].cancelled is True
        assert created_timers[3].cancelled is True
    finally:
        configure({"digest": {}})
