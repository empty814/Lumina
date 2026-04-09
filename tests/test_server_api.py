"""
API 契约测试：验证端点的请求/响应结构，不依赖真实 LLM 或 PDF 翻译。
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


def _make_app():
    """创建带 mock LLM + Transcriber 的 FastAPI 实例。"""
    from lumina.api.server import create_app
    from lumina.engine.llm import LLMEngine
    from lumina.asr.transcriber import Transcriber

    llm = MagicMock(spec=LLMEngine)
    llm.is_loaded = True
    llm.generate = AsyncMock(return_value="mocked response")
    llm.generate_stream = AsyncMock(return_value=aiter(["hello", " world"]))

    transcriber = MagicMock(spec=Transcriber)
    transcriber.model = "mock-whisper"
    transcriber.transcribe = AsyncMock(return_value="transcribed text")

    return create_app(llm, transcriber)


async def aiter(items):
    for item in items:
        yield item


@pytest.fixture
def app():
    return _make_app()


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


# ── 健康检查 ─────────────────────────────────────────────────────────────────

async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ── 版本同步 ─────────────────────────────────────────────────────────────────

async def test_openapi_version_matches_package(client):
    r = await client.get("/openapi.json")
    assert r.status_code == 200
    info = r.json()["info"]
    assert info["version"] != "0.1.0", "FastAPI version still hardcoded to 0.1.0"


# ── Chat Completions ──────────────────────────────────────────────────────────

async def test_chat_completions_basic(client):
    r = await client.post("/v1/chat/completions", json={
        "model": "lumina",
        "messages": [{"role": "user", "content": "hello"}],
    })
    assert r.status_code == 200
    data = r.json()
    assert data["choices"][0]["message"]["role"] == "assistant"
    assert data["choices"][0]["message"]["content"] == "mocked response"


async def test_chat_completions_missing_messages(client):
    r = await client.post("/v1/chat/completions", json={"model": "lumina"})
    assert r.status_code == 422


# ── PDF URL 端点 Pydantic 校验 ────────────────────────────────────────────────

async def test_pdf_url_missing_url_returns_422(client):
    """缺少 url 字段应返回 422，不是 400。"""
    r = await client.post("/v1/pdf/url", json={"lang_out": "zh"})
    assert r.status_code == 422


async def test_pdf_url_stream_missing_url_returns_422(client):
    r = await client.post("/v1/pdf/url_stream", json={"lang_out": "zh"})
    assert r.status_code == 422


async def test_pdf_url_valid_request_accepted(client):
    """有效请求应被接受（翻译过程会失败，但 422 不应出现）。"""
    # 只检查不是 422；下载失败会 400，这是预期的
    with patch("httpx.AsyncClient.get", side_effect=Exception("network")):
        r = await client.post("/v1/pdf/url", json={"url": "http://example.com/a.pdf"})
    assert r.status_code != 422


# ── Translate / Summarize / Polish ──────────────────────────────────────────

async def test_translate(client):
    r = await client.post("/v1/translate", json={"text": "hello"})
    assert r.status_code == 200
    assert "text" in r.json()


async def test_translate_missing_text(client):
    r = await client.post("/v1/translate", json={})
    assert r.status_code == 422


async def test_summarize(client):
    r = await client.post("/v1/summarize", json={"text": "long article"})
    assert r.status_code == 200
    assert "text" in r.json()


async def test_polish_zh(client):
    r = await client.post("/v1/polish", json={"text": "文字", "language": "zh"})
    assert r.status_code == 200


async def test_polish_invalid_language(client):
    r = await client.post("/v1/polish", json={"text": "text", "language": "fr"})
    assert r.status_code == 422


# ── 模型列表 ─────────────────────────────────────────────────────────────────

async def test_list_models(client):
    r = await client.get("/v1/models")
    assert r.status_code == 200
    ids = [m["id"] for m in r.json()["data"]]
    assert "lumina" in ids


# ── PDF Job 状态 ──────────────────────────────────────────────────────────────

async def test_pdf_job_not_found(client):
    r = await client.get("/v1/pdf/job/nonexistent")
    assert r.status_code == 404


async def test_pdf_download_not_found(client):
    r = await client.get("/v1/pdf/download/nonexistent/mono")
    assert r.status_code == 404
