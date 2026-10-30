import json
import os
from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse

from core.agent import travel_agent
from core.log_manager import get_logger

logger = get_logger(__name__)

app = FastAPI(title="Smart Travel Agent API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.getenv(
            "FRONTEND_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        ).split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=20_000)


def _text_from_chunk(chunk: Any) -> str:
    content = getattr(chunk, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and isinstance(item.get("text"), str)
        )
    return ""


def _event(event_name: str, data: dict[str, Any]) -> str:
    return f"event: {event_name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _stream_agent_response(request: ChatRequest) -> AsyncIterator[str]:
    emitted_text = False
    try:
        config = {"configurable": {"thread_id": request.session_id}}
        async for event in travel_agent.astream_events(
            {"messages": [{"role": "user", "content": request.message}]},
            config=config,
            version="v2",
        ):
            metadata = event.get("metadata", {})
            if (
                event.get("event") == "on_chat_model_stream"
                and metadata.get("langgraph_node") == "model"
            ):
                text = _text_from_chunk(event.get("data", {}).get("chunk"))
                if text:
                    emitted_text = True
                    yield _event("token", {"text": text})
            elif event.get("event") == "on_chain_end" and event.get("name") == "LangGraph":
                if not emitted_text:
                    output = event.get("data", {}).get("output", {})
                    messages = output.get("messages", []) if isinstance(output, dict) else []
                    for message in reversed(messages):
                        if getattr(message, "type", None) == "ai":
                            text = _text_from_chunk(message)
                            if text:
                                yield _event("token", {"text": text})
                                emitted_text = True
                                break

        yield _event("done", {})
    except Exception as error:
        logger.exception("Streaming travel-agent request failed")
        yield _event("error", {"message": str(error)})


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    logger.info("Starting streamed chat for session %s", request.session_id)
    return StreamingResponse(
        _stream_agent_response(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
