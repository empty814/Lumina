"""
lumina/api/routers/text.py — 翻译 / 摘要 / 润色路由
"""
import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from lumina.api.protocol import (
    PolishRequest,
    SummarizeRequest,
    TextResponse,
    TranslateRequest,
)

router = APIRouter(tags=["text"])

_llm = None
logger = logging.getLogger("lumina")


def init_router(llm) -> None:
    global _llm
    _llm = llm


@router.post("/v1/translate")
async def translate(request: TranslateRequest):
    task = "translate_to_zh" if request.target_language == "zh" else "translate_to_en"
    if request.stream:
        return StreamingResponse(
            _stream_text(request.text, task),
            media_type="text/event-stream",
        )
    text = await _llm.generate(request.text, task=task)
    return TextResponse(text=text)


@router.post("/v1/summarize")
async def summarize(request: SummarizeRequest):
    if request.stream:
        return StreamingResponse(
            _stream_text(request.text, "summarize"),
            media_type="text/event-stream",
        )
    text = await _llm.generate(request.text, task="summarize")
    return TextResponse(text=text)


@router.post("/v1/polish")
async def polish(request: PolishRequest):
    task = "polish_zh" if request.language == "zh" else "polish_en"
    if request.stream:
        return StreamingResponse(
            _stream_text(request.text, task),
            media_type="text/event-stream",
        )
    text = await _llm.generate(request.text, task=task)
    return TextResponse(text=text)


async def _stream_text(user_text: str, task: str):
    try:
        async for token in _llm.generate_stream(user_text, task=task):
            yield f"data: {json.dumps({'text': token})}\n\n"
    except Exception as e:
        logger.error("stream_text error: %s", e)
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
    yield "data: [DONE]\n\n"
