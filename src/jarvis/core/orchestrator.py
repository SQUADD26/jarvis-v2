import asyncio
from typing import Literal
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage

from jarvis.core.state import JarvisState, INTENT_CATEGORIES
from jarvis.core.router import router
from jarvis.core.planner import planner
from jarvis.core.memory import memory
from jarvis.core.freshness import freshness
from jarvis.agents import AGENTS
from jarvis.integrations.gemini import gemini
from jarvis.db.repositories import ChatRepository
from jarvis.utils.logging import get_logger

logger = get_logger(__name__)

# Semaphore to limit concurrent fact extraction tasks
_fact_extraction_semaphore = asyncio.Semaphore(3)

# System prompt for Jarvis
JARVIS_SYSTEM_PROMPT = """Sei JARVIS, assistente personale. Rispondi in italiano.

REGOLE:
- Sii diretto, pratico, veloce
- NIENTE battute, ironia, o commenti inutili
- Rispondi SOLO a quello che è stato chiesto
- Se hai dati, usali. Se non li hai, dillo brevemente
- Riassumi quando ci sono tanti dati, non fare liste infinite

FORMATTAZIONE TELEGRAM:
- <b>grassetto</b> solo per cose importanti
- <i>corsivo</i> per dettagli secondari
- Scrivi in modo naturale, non schematico

DATI UTENTE:
{memory_facts}

DATI AGENTI:
{agent_data}
"""


async def analyze_intent(state: JarvisState) -> JarvisState:
    """Analyze user intent and determine required agents."""
    user_input = state["current_input"]
    user_id = state["user_id"]

    # Use semantic router first (fast, no LLM call)
    intent, confidence = await router.route(user_input)

    # Get required agents from router
    required_agents = router.get_required_agents(intent)

    # If intent is complex/unknown OR confidence is low, use LLM planner
    if intent in ("complex", "unknown") or (confidence < 0.80 and not required_agents):
        logger.info(f"Router uncertain (intent={intent}, conf={confidence:.2f}), using planner...")
        planned_agents = await planner.plan(user_input, user_id)

        if planned_agents:
            required_agents = planned_agents
            intent = "planned"  # Mark as planned for logging
        # If planner returns empty, it's likely chitchat - keep as is

    logger.info(f"Intent: {intent} (confidence={confidence:.2f}), agents: {required_agents}")

    return {
        **state,
        "intent": intent,
        "intent_confidence": confidence,
        "required_agents": required_agents
    }


async def load_memory(state: JarvisState) -> JarvisState:
    """Load relevant memory facts."""
    user_id = state["user_id"]
    user_input = state["current_input"]

    # Retrieve relevant facts
    try:
        facts = await memory.retrieve_relevant_facts(user_id, user_input, limit=5)
    except Exception as e:
        logger.warning(f"Failed to load memory: {e}")
        facts = []

    logger.debug(f"Loaded {len(facts)} memory facts")

    return {
        **state,
        "memory_context": facts
    }


async def check_freshness(state: JarvisState) -> JarvisState:
    """Check which resources need fresh data."""
    user_id = state["user_id"]
    required_agents = state["required_agents"]

    # Map agents to resource types
    resource_types = list(set([
        AGENTS[agent].resource_type
        for agent in required_agents
        if agent in AGENTS
    ]))

    # Check freshness for each resource
    needs_refresh = await freshness.check_all(user_id, resource_types)

    logger.debug(f"Freshness check: {needs_refresh}")

    return {
        **state,
        "needs_refresh": needs_refresh
    }


async def execute_agents(state: JarvisState) -> JarvisState:
    """Execute required agents in parallel."""
    required_agents = state["required_agents"]

    if not required_agents:
        return {**state, "agent_results": {}}

    # Execute all agents in parallel
    tasks = []
    for agent_name in required_agents:
        if agent_name in AGENTS:
            tasks.append(AGENTS[agent_name].execute(state))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results
    agent_results = {}
    for agent_name, result in zip(required_agents, results):
        if isinstance(result, Exception):
            logger.error(f"Agent {agent_name} failed: {result}")
            agent_results[agent_name] = {
                "agent_name": agent_name,
                "success": False,
                "data": None,
                "error": str(result)
            }
        else:
            agent_results[agent_name] = result

    logger.info(f"Executed {len(agent_results)} agents")

    return {
        **state,
        "agent_results": agent_results
    }


async def generate_response(state: JarvisState) -> JarvisState:
    logger.info("Generating response...")
    """Generate final response using LLM."""
    intent = state["intent"]
    agent_results = state["agent_results"]
    memory_facts = state["memory_context"]
    messages = state["messages"]

    # For chitchat, simple response
    if intent == "chitchat":
        response = await gemini.generate(
            state["current_input"],
            system_instruction="Sei JARVIS, assistente personale. Rispondi in italiano. Sii breve e diretto, niente battute o commenti inutili. NON scrivere codice.",
            model="gemini-2.5-flash",
            temperature=0.5
        )
        return {
            **state,
            "final_response": response,
            "response_generated": True
        }

    # Format agent data for context
    agent_data_str = ""
    for agent_name, result in agent_results.items():
        if result.get("success"):
            agent_data_str += f"\n[{agent_name.upper()}]\n{result.get('data')}\n"
        else:
            agent_data_str += f"\n[{agent_name.upper()}] Errore: {result.get('error')}\n"

    # Format memory facts
    memory_str = "\n".join([f"- {fact}" for fact in memory_facts]) if memory_facts else "Nessun fatto memorizzato"

    # Build system prompt
    system_prompt = JARVIS_SYSTEM_PROMPT.format(
        memory_facts=memory_str,
        agent_data=agent_data_str
    )

    # Convert messages to list format
    msg_list = [
        {"role": "user" if isinstance(m, HumanMessage) else "assistant", "content": m.content}
        for m in messages
    ]

    # Generate response with Gemini 2.5 Flash for better quality
    response = await gemini.generate_with_history(
        messages=msg_list,
        system_instruction=system_prompt,
        model="gemini-2.5-flash",
        temperature=0.7
    )

    return {
        **state,
        "final_response": response,
        "response_generated": True
    }


async def _safe_extract_facts(user_id: str, messages: list[dict]):
    """Safely extract facts with error handling and concurrency control."""
    async with _fact_extraction_semaphore:
        try:
            await memory.extract_and_save_facts(user_id, messages)
        except Exception as e:
            logger.error(f"Background fact extraction failed for user {user_id}: {e}")


async def extract_facts(state: JarvisState) -> JarvisState:
    """Extract facts from conversation to save in memory."""
    user_id = state["user_id"]
    messages = state["messages"]

    # Only extract if we have recent messages
    if len(messages) >= 2:
        recent_messages = [
            {"role": "user" if isinstance(m, HumanMessage) else "assistant", "content": m.content}
            for m in messages[-4:]  # Last 4 messages
        ]

        # Extract and save facts (async with error handling)
        asyncio.create_task(_safe_extract_facts(user_id, recent_messages))

    return state


def should_use_agents(state: JarvisState) -> Literal["use_agents", "direct_response"]:
    """Decide if we need to use agents or can respond directly."""
    if state["intent"] == "chitchat" or not state["required_agents"]:
        return "direct_response"
    return "use_agents"


def build_graph() -> StateGraph:
    """Build the Jarvis orchestrator graph."""
    graph = StateGraph(JarvisState)

    # Add nodes
    graph.add_node("analyze_intent", analyze_intent)
    graph.add_node("load_memory", load_memory)
    graph.add_node("check_freshness", check_freshness)
    graph.add_node("execute_agents", execute_agents)
    graph.add_node("generate_response", generate_response)
    graph.add_node("extract_facts", extract_facts)

    # Set entry point
    graph.set_entry_point("analyze_intent")

    # Add edges
    graph.add_edge("analyze_intent", "load_memory")
    graph.add_conditional_edges(
        "load_memory",
        should_use_agents,
        {
            "use_agents": "check_freshness",
            "direct_response": "generate_response"
        }
    )
    graph.add_edge("check_freshness", "execute_agents")
    graph.add_edge("execute_agents", "generate_response")
    graph.add_edge("generate_response", "extract_facts")
    graph.add_edge("extract_facts", END)

    return graph.compile()


# Compiled graph
jarvis_graph = build_graph()


async def process_message(user_id: str, message: str, history: list = None) -> str:
    """Main entry point to process a user message."""
    # Set user context for LLM logging
    gemini.set_user_context(user_id)

    # Build initial state
    messages = history or []
    messages.append(HumanMessage(content=message))

    initial_state: JarvisState = {
        "user_id": user_id,
        "messages": messages,
        "current_input": message,
        "intent": "",
        "intent_confidence": 0.0,
        "required_agents": [],
        "agent_results": {},
        "needs_refresh": {},
        "memory_context": [],
        "final_response": None,
        "response_generated": False
    }

    # Run the graph
    final_state = await jarvis_graph.ainvoke(initial_state)

    # Save to chat history
    try:
        await ChatRepository.save_message(user_id, "user", message)
        await ChatRepository.save_message(user_id, "assistant", final_state["final_response"])
    except Exception as e:
        logger.warning(f"Failed to save chat history: {e}")

    return final_state["final_response"]
