from langchain.agents import create_agent

from core.log_manager import get_logger

logger = get_logger(__name__)


def get_weather(city: str) -> str:
    """Get weather for a given city."""
    return f"It's always sunny in {city}!"


agent = create_agent(
    model="groq:openai/gpt-oss-120b",
    tools=[get_weather],
    system_prompt="You are a helpful assistant",
)

# Run the agent
results = agent.invoke(
    {"messages": [{"role": "user", "content": "what is the weather in sf"}]}
)

final_message = results["messages"][-1].content
logger.info("%s", final_message)
