"""
Lumina HTTP 服务

提供 OpenAI 兼容接口 + 语音录制转写接口 + PWA 前端。
路由逻辑拆分到 lumina/api/routers/，业务服务在 lumina/services/。
"""
import asyncio
import sys as _sys
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from lumina.asr.transcriber import Transcriber
from lumina.engine.llm import LLMEngine

try:
    from importlib.metadata import version as _pkg_version
    _LUMINA_VERSION = _pkg_version("lumina")
except Exception:
    _LUMINA_VERSION = "0.3.0"

# 服务启动时间戳，用于前端检测服务重启
_SERVER_START_TIME = time.time()

# ── 静态文件路径 ───────────────────────────────────────────────────────────────
_STATIC_DIR = (
    Path(_sys._MEIPASS) / "lumina" / "api" / "static"
    if hasattr(_sys, "_MEIPASS")
    else Path(__file__).parent / "static"
)


def create_app(llm: LLMEngine, transcriber: Transcriber) -> FastAPI:
    from lumina.services.pdf import PdfJobManager
    from lumina.api.routers import pdf as pdf_router
    from lumina.api.routers import chat as chat_router
    from lumina.api.routers import digest as digest_router
    from lumina.api.routers import audio as audio_router
    from lumina.api.routers import text as text_router

    app = FastAPI(title="Lumina", version=_LUMINA_VERSION)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 初始化各 router，注入依赖
    manager = PdfJobManager()
    pdf_router.init_router(manager, llm)
    chat_router.init_router(llm)
    digest_router.init_router(llm, _SERVER_START_TIME)
    audio_router.init_router(transcriber)
    text_router.init_router(llm)

    # 注册 router
    app.include_router(pdf_router.router)
    app.include_router(chat_router.router)
    app.include_router(digest_router.router)
    app.include_router(audio_router.router)
    app.include_router(text_router.router)

    # ── PWA 前端 ──────────────────────────────────────────────────────────────

    @app.get("/")
    async def pwa_index():
        return FileResponse(_STATIC_DIR / "index.html", media_type="text/html")

    @app.get("/logo.svg")
    async def pwa_logo():
        return FileResponse(_STATIC_DIR / "logo.svg", media_type="image/svg+xml")

    @app.get("/manifest.json")
    async def pwa_manifest():
        return JSONResponse({
            "name": "Lumina",
            "short_name": "Lumina",
            "description": "本地 AI 翻译与摘要",
            "start_url": "/",
            "display": "standalone",
            "background_color": "#ffffff",
            "theme_color": "#007aff",
            "icons": [
                {"src": "/logo.svg", "sizes": "256x256", "type": "image/svg+xml", "purpose": "any"}
            ]
        })

    # ── 健康检查 ─────────────────────────────────────────────────────────────

    @app.get("/health")
    async def health():
        return {"status": "ok", "llm_loaded": llm.is_loaded}

    # ── 模型列表 ─────────────────────────────────────────────────────────────

    @app.get("/v1/models")
    async def list_models():
        from lumina.api.protocol import ModelCard, ModelList
        return ModelList(
            data=[
                ModelCard(id="lumina"),
                ModelCard(id="lumina-whisper"),
            ]
        )

    return app


async def raw_request_disconnected(request) -> bool:
    """辅助函数，检查客户端是否断开（流式场景）。"""
    try:
        return await asyncio.wait_for(request.is_disconnected(), timeout=0.001)
    except asyncio.TimeoutError:
        return False
    except Exception:
        return False
