import asyncio
import json
import threading
import time
from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import HumanMessage

from core.log_manager import get_logger

logger = get_logger(__name__)

MODEL_TPM_LIMIT = 8_000
APP_TPM_BUDGET = MODEL_TPM_LIMIT - 1_500
MAX_COMPLETION_TOKENS = 1_000
MAX_INPUT_ESTIMATE = APP_TPM_BUDGET - MAX_COMPLETION_TOKENS - 256
WINDOW_SECONDS = 60


class SlidingWindowTokenLimiter:
    """Conservatively reserve model tokens across requests in this process."""

    def __init__(self, budget: int = APP_TPM_BUDGET) -> None:
        self.budget = budget
        self._reservations: dict[int, tuple[float | None, int]] = {}
        self._next_reservation_id = 0
        self._lock = threading.Lock()

    def acquire(self, tokens: int) -> int:
        if tokens > self.budget:
            raise ValueError(
                f"This request needs an estimated {tokens} tokens, above the "
                f"application's {self.budget}-token/minute safety budget. "
                "Shorten the request and try again."
            )

        while True:
            with self._lock:
                now = time.monotonic()
                self._reservations = {
                    reservation_id: (completed_at, amount)
                    for reservation_id, (completed_at, amount) in self._reservations.items()
                    if completed_at is None
                    or now - completed_at < WINDOW_SECONDS
                }
                used = sum(amount for _, amount in self._reservations.values())
                if used + tokens <= self.budget:
                    reservation_id = self._next_reservation_id
                    self._next_reservation_id += 1
                    self._reservations[reservation_id] = (None, tokens)
                    return reservation_id

                completed_at = [
                    finished
                    for finished, _ in self._reservations.values()
                    if finished is not None
                ]
                wait_seconds = (
                    max(0.01, min(completed_at) + WINDOW_SECONDS - now)
                    if completed_at
                    else 1.0
                )

            logger.info(
                "Waiting %.1f seconds for the Groq token budget to replenish",
                wait_seconds,
            )
            time.sleep(wait_seconds)

    def complete(self, reservation_id: int) -> None:
        with self._lock:
            completed_at, tokens = self._reservations[reservation_id]
            if completed_at is None:
                self._reservations[reservation_id] = (time.monotonic(), tokens)


def _request_payload(request: ModelRequest[Any], messages: list[Any]) -> bytes:
    tool_schemas = []
    for tool in request.tools:
        if hasattr(tool, "tool_call_schema"):
            tool_schemas.append(
                {
                    "name": getattr(tool, "name", ""),
                    "description": getattr(tool, "description", ""),
                    "schema": tool.tool_call_schema.model_json_schema(),
                }
            )
        else:
            tool_schemas.append(tool)

    payload = {
        "system": (
            request.system_message.model_dump(mode="json")
            if request.system_message is not None
            else None
        ),
        "messages": [message.model_dump(mode="json") for message in messages],
        "tools": tool_schemas,
    }
    return json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")


def _estimated_input_tokens(request: ModelRequest[Any], messages: list[Any]) -> int:
    # UTF-8 bytes are a conservative upper bound for text-token counts.
    return len(_request_payload(request, messages)) + 256


def _messages_within_budget(request: ModelRequest[Any]) -> list[Any]:
    messages = request.messages
    user_indexes = [
        index for index, message in enumerate(messages)
        if isinstance(message, HumanMessage)
    ]
    if not user_indexes:
        return messages

    latest_user_index = user_indexes[-1]
    starts = [user_indexes[-2], latest_user_index] if len(user_indexes) > 1 else [latest_user_index]
    for start in starts:
        candidate = messages[start:]
        if _estimated_input_tokens(request, candidate) <= MAX_INPUT_ESTIMATE:
            return candidate

    latest_turn = messages[latest_user_index:]
    estimated = _estimated_input_tokens(request, latest_turn)
    if estimated > MAX_INPUT_ESTIMATE:
        raise ValueError(
            f"This request is too large for the safe token budget "
            f"(estimated input: {estimated} tokens). Shorten the request and try again."
        )
    return latest_turn


class TokenBudgetMiddleware(AgentMiddleware):
    def __init__(self) -> None:
        super().__init__()
        self._limiter = SlidingWindowTokenLimiter()

    def _prepare(self, request: ModelRequest[Any]) -> tuple[ModelRequest[Any], int]:
        messages = _messages_within_budget(request)
        input_estimate = _estimated_input_tokens(request, messages)
        reservation = input_estimate + MAX_COMPLETION_TOKENS
        return request.override(messages=messages), reservation

    def wrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], ModelResponse[Any]],
    ) -> ModelResponse[Any]:
        bounded_request, reservation = self._prepare(request)
        reservation_id = self._limiter.acquire(reservation)
        try:
            return handler(bounded_request)
        finally:
            self._limiter.complete(reservation_id)

    async def awrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], Awaitable[ModelResponse[Any]]],
    ) -> ModelResponse[Any]:
        bounded_request, reservation = self._prepare(request)
        reservation_id = await asyncio.to_thread(self._limiter.acquire, reservation)
        try:
            return await handler(bounded_request)
        finally:
            self._limiter.complete(reservation_id)
