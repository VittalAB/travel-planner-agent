from langgraph.checkpoint.memory import MemorySaver
from langchain.agents import create_agent

from core.tools import duckduckgo_search, flight_price_search, get_current_date
from core.log_manager import get_logger
from core.prompts import TRAVEL_AGENT_SYSTEM_PROMPT
from core.middleware.date_context import CurrentDateMiddleware
from core.middleware.gaurdrail import intent_guardrail

logger = get_logger(__name__)

# Session-level in-memory checkpointer
memory = MemorySaver()

# Standard single-agent workflow using LangChain's create_agent
travel_agent = create_agent(
    model="groq:openai/gpt-oss-120b",
    tools=[duckduckgo_search, flight_price_search, get_current_date],
    checkpointer=memory,
    system_prompt=TRAVEL_AGENT_SYSTEM_PROMPT,
    middleware=[CurrentDateMiddleware()],
)

logger.debug("Travel agent initialized")
