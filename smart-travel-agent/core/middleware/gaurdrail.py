from typing import Any

from langchain.agents.middleware import AgentState, before_agent
from langchain_groq import ChatGroq
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.runtime import Runtime

from core.log_manager import get_logger
from core.prompts import _CLASSIFIER_PROMPT, OFF_TOPIC_REPLY

logger = get_logger(__name__)
CLASSIFIER_MAX_TOKENS = 128
CLASSIFICATION_FAILURE_REPLY = (
    "I couldn't reliably check whether that request is travel-related. "
    "Please rephrase it as a travel question."
)
MIXED_REQUEST_REPLY = (
    "I can only help with travel-related questions. Your message includes "
    "another topic too; please send just the travel-related part."
)
safety_model = ChatGroq(
    model="openai/gpt-oss-120b",
    temperature=0,
    reasoning_effort="low",
    max_tokens=CLASSIFIER_MAX_TOKENS,
)


def _response_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return " ".join(
            item.get("text", "").strip()
            for item in content
            if isinstance(item, dict)
            and isinstance(item.get("text"), str)
            and item.get("text", "").strip()
        ).strip()
    return ""


@before_agent(can_jump_to=["end"])
def intent_guardrail(
    state: AgentState,
    runtime: Runtime,
) -> dict[str, Any] | None:
    """Prevent requests unrelated to travel from reaching the travel agent."""
    messages = state.get("messages", [])
    latest_user_index = next(
        (
            index
            for index in range(len(messages) - 1, -1, -1)
            if isinstance(messages[index], HumanMessage)
        ),
        None,
    )
    if latest_user_index is None:
        return None

    latest_user_message = messages[latest_user_index]
    prior_user_messages = [
        message.content
        for message in messages[:latest_user_index]
        if isinstance(message, HumanMessage)
    ][-2:]
    classifier_input = (
        "Prior user context (for resolving short references only):\n"
        + "\n".join(str(content)[:500] for content in prior_user_messages)
        + "\n\nLatest user request to classify:\n"
        + str(latest_user_message.content)[:1_000]
    )
    try:
        result = safety_model.invoke(
            [
                SystemMessage(content=_CLASSIFIER_PROMPT),
                HumanMessage(content=classifier_input),
            ]
        )
    except Exception:
        logger.exception("Intent classifier request failed; blocking request")
        return {
            "messages": [AIMessage(content=CLASSIFICATION_FAILURE_REPLY)],
            "jump_to": "end",
        }

    classification = _response_text(result.content).upper()
    if classification not in {"TRAVEL_ONLY", "MIXED", "OFF_TOPIC"}:
        logger.error(
            "Intent classifier returned an invalid label: %r",
            result.content,
        )
        return {
            "messages": [AIMessage(content=CLASSIFICATION_FAILURE_REPLY)],
            "jump_to": "end",
        }

    logger.info("Classified latest user request as %s", classification)
    if classification == "MIXED":
        return {
            "messages": [AIMessage(content=MIXED_REQUEST_REPLY)],
            "jump_to": "end",
        }
    if classification == "OFF_TOPIC":
        return {
            "messages": [AIMessage(content=OFF_TOPIC_REPLY)],
            "jump_to": "end",
        }
    return None
