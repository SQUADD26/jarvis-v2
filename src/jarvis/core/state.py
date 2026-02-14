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
    enriched_input: str  # Query arricchita con contesto conversazionale

    # Intent analysis
    intent: str  # "calendar_read", "email_write", "complex", etc.
    intent_confidence: float
    required_agents: list[str]

    # Execution
    agent_results: dict[str, AgentResult]
    needs_refresh: dict[str, bool]  # Which resources need fresh data

    # Memory
    memory_context: list[str]  # Retrieved facts
    entity_context: list[dict]  # Retrieved entities from knowledge graph

    # Output
    final_response: Optional[str]
    response_generated: bool

    # Multi-step reasoning
    plan_steps: list[dict]  # [{"agents": [...], "goal": "..."}, ...]
    current_step_index: int
    step_results: list[dict]  # Results from completed steps
    step_retry_count: int
    max_retries: int
    max_steps: int


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
    "kg_query": ["kg"],  # Knowledge graph queries (people, relationships)
    "chitchat": [],  # No agents needed
    "complex": [],   # Fallback - planner will determine agents
    "planned": [],   # Agents determined by LLM planner
    "unknown": []
}
