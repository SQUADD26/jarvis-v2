from typing import TypedDict, Annotated, Optional, Any
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class AgentResult(TypedDict):
    """Result from a sub-agent execution."""
    agent_name: str
    success: bool
    data: Any
    error: Optional[str]


class JarvisState(TypedDict):
    """Main state for Jarvis orchestrator."""

    # User info
    user_id: str

    # Conversation
    messages: Annotated[list[BaseMessage], add_messages]
    current_input: str

    # Intent analysis
    intent: str  # "calendar_read", "email_write", "complex", etc.
    intent_confidence: float
    required_agents: list[str]

    # Execution
    agent_results: dict[str, AgentResult]
    needs_refresh: dict[str, bool]  # Which resources need fresh data

    # Memory
    memory_context: list[str]  # Retrieved facts

    # Output
    final_response: Optional[str]
    response_generated: bool


# Intent categories
INTENT_CATEGORIES = {
    "calendar_read": ["calendar"],
    "calendar_write": ["calendar"],
    "email_read": ["email"],
    "email_write": ["email"],
    "web_search": ["web"],
    "web_scrape": ["web"],
    "rag_query": ["rag"],
    "rag_ingest": ["rag"],
    "chitchat": [],  # No agents needed
    "complex": [],   # Fallback - planner will determine agents
    "planned": [],   # Agents determined by LLM planner
    "unknown": []
}
