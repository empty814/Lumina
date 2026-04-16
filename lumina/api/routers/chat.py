"""
lumina/api/routers/chat.py — Chat Completions 路由（OpenAI 兼容）
"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from lumina.api.chat_runtime import (
    extract_system_override,
    run_chat_messages,
    stream_chat_messages,
    to_provider_messages,
)
from lumina.api.protocol import (
    ChatCompletionChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionStreamChoice,
    ChatCompletionStreamDelta,
    ChatCompletionStreamResponse,
    ChatMessage,
    UsageInfo,
    random_uuid,
)

router = APIRouter(tags=["chat"])

logger = logging.getLogger("lumina")


@router.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest, raw: Request):
    req_id = f"chatcmpl-{random_uuid()}"

    messages = to_provider_messages(request.messages)
    system_override = extract_system_override(request.messages)
    if not any(message["role"] == "user" for message in messages):
        raise HTTPException(status_code=400, detail="No user message found")

    if request.stream:
        return StreamingResponse(
            _stream_chat(request, raw, messages, req_id, system_override),
            media_type="text/event-stream",
        )

    text = await run_chat_messages(
        raw,
        messages=messages,
        task="chat",
        origin="chat_api",
        client_model=request.model,
        request_id=req_id,
        system_override=system_override,
        max_tokens=request.max_tokens,
        temperature=request.temperature,
        top_p=request.top_p,
        top_k=request.top_k,
        min_p=request.min_p,
        presence_penalty=request.presence_penalty,
        repetition_penalty=request.repetition_penalty,
    )
    return ChatCompletionResponse(
        id=req_id,
        model=request.model,
        choices=[
            ChatCompletionChoice(
                message=ChatMessage(role="assistant", content=text)
            )
        ],
        usage=UsageInfo(),
    )


async def _stream_chat(
    request: ChatCompletionRequest,
    raw_req: Request,
    messages: list[dict],
    req_id: str,
    system_override: Optional[str] = None,
):
    from lumina.api.server import raw_request_disconnected

    finish_reason = "stop"
    try:
        async for token in stream_chat_messages(
            raw_req,
            messages=messages,
            task="chat",
            origin="chat_api",
            client_model=request.model,
            request_id=req_id,
            system_override=system_override,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            top_p=request.top_p,
            top_k=request.top_k,
            min_p=request.min_p,
            presence_penalty=request.presence_penalty,
            repetition_penalty=request.repetition_penalty,
        ):
            chunk = ChatCompletionStreamResponse(
                id=req_id,
                model=request.model,
                choices=[
                    ChatCompletionStreamChoice(
                        delta=ChatCompletionStreamDelta(content=token)
                    )
                ],
            )
            yield f"data: {chunk.model_dump_json()}\n\n"
            if await raw_request_disconnected(raw_req):
                break
    except Exception as e:
        logger.error("stream_chat error: %s", e)
        finish_reason = "error"
    end_chunk = ChatCompletionStreamResponse(
        id=req_id,
        model=request.model,
        choices=[
            ChatCompletionStreamChoice(
                delta=ChatCompletionStreamDelta(),
                finish_reason=finish_reason,
            )
        ],
    )
    yield f"data: {end_chunk.model_dump_json()}\n\n"
    yield "data: [DONE]\n\n"
