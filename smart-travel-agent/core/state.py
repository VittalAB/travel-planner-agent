from typing import TypedDict, List, Annotated, Optional, Dict, Any
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


class TripConstraints(BaseModel):
    origin: Optional[str] = Field(None, description="Starting city/country")
    destination: Optional[str] = Field(None, description="Destination city/country")
    budget: Optional[str] = Field(None, description="Budget (e.g. ₹50,000 or $2,000 per person)")
    duration: Optional[str] = Field(None, description="Trip duration (e.g. 5 days)")
    travelers: Optional[str] = Field(None, description="Number/type of travelers (e.g. 2 adults)")
    style: Optional[str] = Field(None, description="Vacation mode/style (Leisure, Adventure, Spiritual, Luxury, Backpacking)")


class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    constraints: Optional[Dict[str, Any]]
    itinerary_data: Optional[Dict[str, Any]]
