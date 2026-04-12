"""
lumina/api/sse.py — SSE 流式响应辅助

公开接口：
    stream_llm  — 将 llm.generate_stream() 包装为 SSE 数据行 AsyncIterator
"""
import json
import logging
from typing import AsyncIterator

logger = logging.getLogger("lumina")


async def stream_llm(llm, user_text: str, *, task: str, log_label: str = "stream") -> AsyncIterator[str]:
    """
    驱动 llm.generate_stream(user_text, task=task)，yield SSE 数据行。

    最后 yield "data: [DONE]\\n\\n"，异常时 yield error 事件。
    """
    try:
        async for token in llm.generate_stream(user_text, task=task):
            yield f"data: {json.dumps({'text': token})}\n\n"
    except Exception as e:
        logger.error("%s error: %s", log_label, e)
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
    yield "data: [DONE]\n\n"
