import asyncio
from typing import Literal
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage

from jarvis.core.state import JarvisState
from jarvis.core.planner import planner
from jarvis.core.memory import memory
from jarvis.core.knowledge_graph import knowledge_graph
from jarvis.core.freshness import freshness
from jarvis.agents import AGENTS
from jarvis.integrations.gemini import gemini
from jarvis.db.repositories import ChatRepository
from jarvis.utils.logging import get_logger

logger = get_logger(__name__)

# Semaphore to limit concurrent fact extraction tasks
_fact_extraction_semaphore = asyncio.Semaphore(3)

# Prompt for query enrichment
ENRICH_QUERY_PROMPT = """Sei un sistema di riscrittura query. Il tuo compito è rendere la query dell'utente AUTOSUFFICIENTE aggiungendo il contesto mancante dalla conversazione recente.

REGOLE:
1. Se la query è già chiara e autosufficiente, restituiscila IDENTICA
2. Se la query contiene riferimenti impliciti (pronomi, "lì", "quello", ecc.), risolvi i riferimenti usando la cronologia
3. Aggiungi SOLO informazioni di contesto essenziali (luogo, persona, argomento)
4. NON aggiungere interpretazioni, opinioni o dettagli non presenti nella conversazione
5. Rispondi SOLO con la query riscritta, nient'altro

CRONOLOGIA RECENTE:
{history}

QUERY ATTUALE: {query}

QUERY RISCRITTA:"""

# System prompt for Jarvis
JARVIS_SYSTEM_PROMPT = """Sei JARVIS, l'assistente personale AI di Roberto Bondici, CTO di Squadd.
Roberto si occupa di automazioni, API, integrazioni, ma anche management con team e clienti.

DATA DI OGGI: {today}

TONO:
- Cordiale e naturale, come un assistente fidato
- Puoi usare "Boss" o "Capo" occasionalmente
- Mai robotico ("Sono operativo"), mai esagerato con battute

REGOLE FONDAMENTALI:
1. RISPONDI SOLO A CIÒ CHE È STATO CHIESTO
   - NON aggiungere informazioni non richieste
   - NON fare "spillover" di contesto non pertinente

2. SII CONCISO E DIRETTO
   - Due-tre frasi massimo per risposte semplici
   - Niente giri di parole, linguaggio naturale
   - Se ci sono tanti dati, riassumi intelligentemente

3. DOMANDE SOLO SE NECESSARIE
   - MAI domande "di cortesia" o per mostrare interesse
   - Chiedi solo se serve per completare un'azione

4. NO INIZIATIVE NON RICHIESTE
   - NON suggerire azioni non chieste
   - NON fare osservazioni su cose non menzionate

5. ⚠️ MAI INVENTARE DATI - REGOLA CRITICA ⚠️
   - I "DATI DAGLI AGENTI" sono l'UNICA fonte di verità per azioni appena eseguite
   - Se DATI DAGLI AGENTI contiene "Errore" → l'azione è FALLITA, dillo chiaramente
   - Se DATI DAGLI AGENTI è vuoto o assente → NON hai fatto nulla, NON fingere di aver controllato
   - MEMORIA UTENTE è solo contesto storico, NON conferma di azioni appena eseguite
   - MAI dire "ho controllato/verificato/confermato X" se NON c'è il risultato ESPLICITO in DATI DAGLI AGENTI
   - MAI confermare che "tutto è ok" o "è corretto" senza MOSTRARE i dati reali
   - Se l'utente chiede di VERIFICARE qualcosa, DEVI mostrare i dati effettivi, non dire "sì è ok"
   - Se un agente fallisce o non viene chiamato, AMMETTILO onestamente

6. QUANDO MOSTRI DATI DEL CALENDARIO:
   - ELENCA gli eventi con orari e titoli
   - Se ci sono più eventi allo stesso orario, SEGNALALO come possibile problema
   - NON dire "tutto ok" - MOSTRA cosa c'è effettivamente

7. QUANDO USI ENTITÀ CONOSCIUTE:
   - Usa le informazioni sulle persone/organizzazioni per contestualizzare le risposte
   - Se l'utente chiede di una persona, usa le proprietà e relazioni note
   - NON inventare dettagli non presenti nelle entità

8. QUANDO MOSTRI TASK/ATTIVITÀ:
   - Raggruppa per database/progetto se ci sono più database
   - Mostra SOLO: titolo, stato, scadenza (se presente), titolare (se presente)
   - Se sono tante (>10), mostra un RIEPILOGO CONTEGGIO per stato (es. "15 Da Fare, 3 In Corso, 2 Completate")
   - Poi elenca SOLO le task urgenti/in scadenza, o le prime 5-8 più rilevanti
   - MAI elencare 20+ task una per una - è illeggibile
   - MAI chiedere "ti sembra adeguata?" o simili domande di cortesia

FORMATTAZIONE (OBBLIGATORIA - USA SOLO QUESTI TAG HTML):
- <b>grassetto</b> per enfasi importante
- <i>corsivo</i> per dettagli secondari
- Per elenchi usa: "- " oppure "1. 2. 3." come testo semplice
- MAI usare: <ol>, <ul>, <li>, <h1>, <h2>, <p>, <div>, <span> o qualsiasi altro tag HTML
- MAI usare Markdown: NO **, NO *, NO ##, NO __, NO ```
- Scrivi naturale, non schematico

MEMORIA UTENTE (contesto storico, NON azioni appena eseguite):
{memory_facts}

ENTITÀ CONOSCIUTE (persone, organizzazioni, relazioni):
{entity_context}

DATI DAGLI AGENTI (risultato REALE delle azioni di QUESTA richiesta):
{agent_data}

IMPORTANTE: Se "DATI DAGLI AGENTI" è vuoto, NON HAI DATI REALI. Non fingere di averli.
"""


async def analyze_intent(state: JarvisState) -> JarvisState:
    """Analyze user intent and determine required agents using LLM planner."""
    user_input = state["current_input"]
    user_id = state["user_id"]
    messages = state.get("messages", [])

    # Pass conversation history to planner for context (exclude current message)
    history = messages[:-1] if len(messages) > 1 else []

    # Always use planner - reliable and fast (Gemini 2.5 Flash)
    required_agents = await planner.plan(user_input, user_id, history=history)

    # Determine intent based on agents
    if required_agents:
        intent = "action"
    else:
        intent = "chitchat"

    logger.info(f"Planner: intent={intent}, agents={required_agents}")

    return {
        **state,
        "intent": intent,
        "intent_confidence": 1.0,  # Planner is always confident
        "required_agents": required_agents
    }


async def load_memory(state: JarvisState) -> JarvisState:
    """Load relevant memory facts and entities in parallel."""
    user_id = state["user_id"]
    user_input = state["current_input"]

    # Retrieve facts and entities in parallel
    facts = []
    entities = []

    try:
        facts_task = memory.retrieve_relevant_facts(user_id, user_input, limit=5)
        entities_task = knowledge_graph.retrieve_relevant_entities(user_id, user_input, limit=5)

        results = await asyncio.gather(facts_task, entities_task, return_exceptions=True)

        # Process facts result
        if isinstance(results[0], Exception):
            logger.warning(f"Failed to load memory facts: {results[0]}")
        else:
            facts = results[0]

        # Process entities result
        if isinstance(results[1], Exception):
            logger.warning(f"Failed to load entities: {results[1]}")
        else:
            entities = results[1]

    except Exception as e:
        logger.warning(f"Failed to load memory/entities: {e}")

    logger.debug(f"Loaded {len(facts)} memory facts, {len(entities)} entities")

    return {
        **state,
        "memory_context": facts,
        "entity_context": entities
    }


async def enrich_query(state: JarvisState) -> JarvisState:
    """Enrich user query with conversational context to make it self-contained."""
    messages = state.get("messages", [])
    current_input = state["current_input"]

    # Skip enrichment if no meaningful history
    if len(messages) <= 1:
        return {**state, "enriched_input": current_input}

    try:
        # Take last 4 messages (excluding current), truncate to 300 chars each
        history_messages = messages[:-1][-4:]
        history_lines = []
        for msg in history_messages:
            role = "Utente" if isinstance(msg, HumanMessage) else "Assistente"
            content = msg.content[:300]
            history_lines.append(f"{role}: {content}")

        history_str = "\n".join(history_lines)

        prompt = ENRICH_QUERY_PROMPT.format(
            history=history_str,
            query=current_input
        )

        enriched = await gemini.generate(
            prompt,
            system_instruction="Riscrivi la query in modo autosufficiente. Rispondi SOLO con la query riscritta.",
            model="gemini-2.5-flash",
            temperature=0,
            max_tokens=256
        )

        if enriched and enriched.strip():
            enriched = enriched.strip()
            logger.info(f"Query enriched: '{current_input}' -> '{enriched}'")
            return {**state, "enriched_input": enriched}

    except Exception as e:
        logger.warning(f"Query enrichment failed, using original: {e}")

    return {**state, "enriched_input": current_input}


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
    entity_context = state.get("entity_context", [])
    messages = state["messages"]

    # For chitchat, use history for context
    if intent == "chitchat":
        # Convert messages to list format for history-aware response
        msg_list = [
            {"role": "user" if isinstance(m, HumanMessage) else "assistant", "content": m.content}
            for m in messages
        ]
        response = await gemini.generate_with_history(
            messages=msg_list,
            system_instruction="Sei JARVIS, assistente personale. Rispondi in italiano, tono cordiale e naturale. Puoi usare 'Boss' o 'Capo' occasionalmente. Breve e diretto, niente risposte robotiche tipo 'Sono operativo'. NON scrivere codice. USA IL CONTESTO della conversazione per capire riferimenti vaghi.",
            model="gemini-2.5-flash",
            temperature=0.6
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

    # Format entity context
    entity_str = knowledge_graph.format_entity_context(entity_context) if entity_context else "Nessuna entita conosciuta"

    # Build system prompt
    from datetime import datetime
    today = datetime.now().strftime("%A %d %B %Y")
    system_prompt = JARVIS_SYSTEM_PROMPT.format(
        today=today,
        memory_facts=memory_str,
        entity_context=entity_str,
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


async def _safe_extract_entities(user_id: str, messages: list[dict]):
    """Safely extract entities with error handling and concurrency control."""
    async with _fact_extraction_semaphore:
        try:
            result = await knowledge_graph.extract_and_store_entities(user_id, messages)
            if result["entities_created"] or result["relationships_created"]:
                logger.info(
                    f"KG extraction: {len(result['entities_created'])} entities created, "
                    f"{len(result['entities_updated'])} updated, "
                    f"{len(result['relationships_created'])} relationships"
                )
        except Exception as e:
            logger.error(f"Background entity extraction failed for user {user_id}: {e}")


async def extract_facts(state: JarvisState) -> JarvisState:
    """Extract facts and entities from conversation to save in memory."""
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

        # Extract and save entities to knowledge graph (async with error handling)
        asyncio.create_task(_safe_extract_entities(user_id, recent_messages))

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
    graph.add_node("enrich_query", enrich_query)
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
            "use_agents": "enrich_query",
            "direct_response": "generate_response"
        }
    )
    graph.add_edge("enrich_query", "check_freshness")
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
        "enriched_input": message,
        "intent": "",
        "intent_confidence": 0.0,
        "required_agents": [],
        "agent_results": {},
        "needs_refresh": {},
        "memory_context": [],
        "entity_context": [],
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
