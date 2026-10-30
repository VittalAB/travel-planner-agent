import re
import uuid
import streamlit as st
from langchain_core.messages import HumanMessage, AIMessage

from core.agent import travel_agent
from core.log_manager import get_logger

logger = get_logger(__name__)

st.set_page_config(page_title="Smart Travel Planner", layout="wide", page_icon="🧭")

# Session-level memory management
if "session_id" not in st.session_state:
    st.session_state.session_id = f"session_{uuid.uuid4().hex[:10]}"
if "messages" not in st.session_state:
    st.session_state.messages = []
if "constraints" not in st.session_state:
    st.session_state.constraints = {}


st.title("🧭 Smart Conversational Travel Agent")
# st.caption("Deterministic Single-Agent Workflow (`create_react_agent`) powered by Groq & DuckDuckGo Search")


with st.sidebar:
    st.header("⚙️ Session & Controls")
    st.caption(f"**Session ID:** `{st.session_state.session_id}`")
    st.caption("🔒 *Memory is active for this session (non-persistent across resets)*")

    if st.button(
        "🔄 Start New Trip / Reset Chat", use_container_width=True, type="secondary"
    ):
        st.session_state.session_id = f"session_{uuid.uuid4().hex[:10]}"
        st.session_state.messages = []
        st.session_state.constraints = {}
        st.rerun()

    st.divider()
    st.markdown("**💡 Example Queries:**")
    st.caption(
        '- *"Plan a 5-day holiday to Switzerland from Delhi with 1.5 lakh budget"*'
    )
    st.caption('- *"Weekend trip to Goa from Bangalore with 15k budget for 2 friends"*')
    st.caption('- *"What are the Schengen visa requirements for Indians?"*')
    st.caption('- *"Spiritual trip to Vaishno Devi with family for 3 days"*')

    if st.session_state.messages:
        transcript = []
        for m in st.session_state.messages:
            role = "🧑 User" if m["role"] == "user" else "🧭 Travel Agent"
            transcript.append(f"### {role}\n\n{m['content']}\n\n---")

        st.download_button(
            label="📥 Download Itinerary / Chat (.md)",
            data="\n\n".join(transcript),
            file_name=f"travel_plan_{st.session_state.session_id}.md",
            mime="text/markdown",
            use_container_width=True,
        )

# Display existing conversation history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Chat input
if prompt := st.chat_input(
    "Ask anything: E.g., Plan a 5-day trip to Switzerland from Delhi, or visit Goa for a weekend..."
):
    logger.info("Received a chat request")
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    config = {"configurable": {"thread_id": st.session_state.session_id}}

    with st.chat_message("assistant"):
        with st.spinner("Searching live facts via DuckDuckGo & planning your trip..."):
            try:
                result = travel_agent.invoke(
                    {"messages": [HumanMessage(content=prompt)]},
                    config=config,
                )
            except Exception:
                logger.exception("Travel agent invocation failed")
                raise

            # Extract the final AI message from the agent execution
            graph_messages = result.get("messages", [])
            assistant_replies = [
                m.content
                for m in graph_messages
                if isinstance(m, AIMessage) and m.content
            ]

            if assistant_replies:
                final_text = assistant_replies[-1]
                st.markdown(final_text)
                st.session_state.messages.append(
                    {"role": "assistant", "content": final_text}
                )
                logger.info("Travel agent completed the chat request")
            else:
                fallback_reply = "I've reviewed your request. Could you clarify where you'd like to travel or your preferred dates?"
                st.markdown(fallback_reply)
                st.session_state.messages.append(
                    {"role": "assistant", "content": fallback_reply}
                )
                logger.warning("Travel agent returned no assistant response")
