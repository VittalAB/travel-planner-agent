from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import SystemMessage

INDIA_TIMEZONE = ZoneInfo("Asia/Kolkata")


def current_date_context(now: datetime | None = None) -> str:
    current_time = now.astimezone(INDIA_TIMEZONE) if now else datetime.now(INDIA_TIMEZONE)
    return (
        f"Current date and time: {current_time:%A, %d %B %Y, %H:%M} "
        "India Standard Time (Asia/Kolkata). Use this as the present date; "
        "do not infer the current year from training data."
    )


class CurrentDateMiddleware(AgentMiddleware):
    def __init__(self) -> None:
        super().__init__()

    @staticmethod
    def _request_with_current_date(
        request: ModelRequest[Any],
    ) -> ModelRequest[Any]:
        if request.system_message is not None:
            system_message = request.system_message.model_copy(
                update={
                    "content": (
                        f"{request.system_message.content}\n\n"
                        f"{current_date_context()}"
                    )
                }
            )
        else:
            system_message = SystemMessage(content=current_date_context())
        return request.override(system_message=system_message)

    def wrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], ModelResponse[Any]],
    ) -> ModelResponse[Any]:
        return handler(self._request_with_current_date(request))

    async def awrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[
            [ModelRequest[Any]], Awaitable[ModelResponse[Any]]
        ],
    ) -> ModelResponse[Any]:
        return await handler(self._request_with_current_date(request))
