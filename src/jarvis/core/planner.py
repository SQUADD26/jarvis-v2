"""LLM-based planner for complex intent routing."""

import json
from jarvis.integrations.gemini import gemini
from jarvis.utils.logging import get_logger

logger = get_logger(__name__)

# Available agents and their capabilities
AGENT_CAPABILITIES = {
    "calendar": "Accesso al calendario Google: leggere eventi, CREARE nuovi eventi, modificare, cancellare, bloccare slot, fissare appuntamenti",
    "email": "Accesso a Gmail: leggere email, scrivere email, creare bozze, rispondere, cercare messaggi",
    "web": "Ricerca web: cercare informazioni online, meteo, notizie, fatti attuali",
    "rag": "Knowledge base personale: cercare nei documenti dell'utente, file caricati, note",
    "kg": "Knowledge graph personale: informazioni su persone, organizzazioni, colleghi, relazioni. Domande come 'chi e X?', 'chi sono i miei colleghi?', 'per chi lavora X?', 'dimmi di piu su Y'",
    "task": "Gestione task su Notion: leggere, creare, aggiornare, completare task. Database multipli (personale, lavoro, progetti). Scadenze, priorita, stati."
}

PLANNER_PROMPT = """Sei un planner che decide quali agenti attivare per rispondere alla richiesta dell'utente.
Puoi pianificare AZIONI SEQUENZIALI quando servono piu passaggi.

AGENTI DISPONIBILI:
{agent_descriptions}

REGOLE:
1. Analizza cosa l'utente sta chiedendo, CONSIDERANDO IL CONTESTO della conversazione recente
2. Seleziona SOLO gli agenti necessari
3. Se la richiesta e semplice conversazione (saluti, ringraziamenti), restituisci steps vuoto
4. Se serve UN SOLO passaggio (caso comune), restituisci UN singolo step
5. Se servono AZIONI SEQUENZIALI (output di un agente serve come input per un altro), usa PIU step
6. MASSIMO 3 step per richiesta
7. Se l'utente fa riferimento a qualcosa detto prima, USA IL CONTESTO

REGOLA CRITICA - VERIFICA/CONTROLLA:
Quando l'utente chiede di VERIFICARE, CONTROLLARE, CONFERMARE qualcosa,
DEVI SEMPRE attivare l'agente corrispondente per recuperare i dati REALI.

QUANDO USARE MULTI-STEP:
- "cerca l'email di Marco e crea un evento" -> step1: email (cerca), step2: calendar (crea con dati email)
- "controlla il calendario e manda un riassunto via email" -> step1: calendar, step2: email
- "cerca info su X nel web e salvale nella knowledge base" -> step1: web, step2: rag

QUANDO NON USARE MULTI-STEP (un singolo step basta):
- "cosa ho domani" -> step1: calendar
- "controlla email e calendario" -> step1: calendar + email (paralleli nello stesso step)
- "ciao come stai" -> steps: []

ESEMPI:
- "ciao" -> {{"steps": [], "reasoning": "conversazione"}}
- "cosa ho domani" -> {{"steps": [{{"agents": ["calendar"], "goal": "recupera eventi di domani"}}], "reasoning": "query calendario"}}
- "controlla email e calendario" -> {{"steps": [{{"agents": ["calendar", "email"], "goal": "recupera eventi e email"}}], "reasoning": "query parallela"}}
- "cerca l'email di Marco e crea un evento basato su quella" -> {{"steps": [{{"agents": ["email"], "goal": "cerca email da Marco"}}, {{"agents": ["calendar"], "goal": "crea evento basato sui dati dell'email trovata"}}], "reasoning": "azione sequenziale: prima email poi calendario"}}

Rispondi SOLO con un JSON valido:
{{"steps": [{{"agents": ["agent1"], "goal": "descrizione obiettivo step"}}], "reasoning": "breve spiegazione"}}

{conversation_context}
RICHIESTA UTENTE ATTUALE:
{user_input}

JSON:"""


class Planner:
    """LLM-based planner for determining required agents."""

    def __init__(self):
        self.model = "gemini-2.5-flash"

    async def plan(self, user_input: str, user_id: str = None, history: list = None) -> tuple[list[str], list[dict]]:
        """
        Analyze user input and determine which agents are needed.

        Returns:
            Tuple of (flat agent list for backward compat, list of step dicts)
        """
        agent_descriptions = "\n".join([
            f"- {name}: {desc}" for name, desc in AGENT_CAPABILITIES.items()
        ])

        conversation_context = ""
        if history and len(history) > 0:
            recent = history[-4:]
            context_lines = ["CONTESTO CONVERSAZIONE RECENTE:"]
            for msg in recent:
                role = "Utente" if msg.__class__.__name__ == "HumanMessage" else "Assistente"
                content = msg.content[:200] + "..." if len(msg.content) > 200 else msg.content
                context_lines.append(f"{role}: {content}")
            conversation_context = "\n".join(context_lines) + "\n\n"

        prompt = PLANNER_PROMPT.format(
            agent_descriptions=agent_descriptions,
            user_input=user_input,
            conversation_context=conversation_context
        )

        try:
            if user_id:
                gemini.set_user_context(user_id)

            response = await gemini.generate(
                prompt,
                model=self.model,
                temperature=0.1
            )

            clean_response = response.strip()
            if clean_response.startswith("```"):
                clean_response = clean_response.split("```")[1]
                if clean_response.startswith("json"):
                    clean_response = clean_response[4:]
                clean_response = clean_response.strip()

            result = json.loads(clean_response)
            steps = result.get("steps", [])
            reasoning = result.get("reasoning", "")

            # Validate steps
            valid_steps = []
            all_agents = []
            for step in steps[:3]:  # Max 3 steps
                agents = [a for a in step.get("agents", []) if a in AGENT_CAPABILITIES]
                if agents:
                    valid_steps.append({
                        "agents": agents,
                        "goal": step.get("goal", "")
                    })
                    all_agents.extend(agents)

            unique_agents = list(dict.fromkeys(all_agents))

            logger.info(f"Planner decision: {len(valid_steps)} steps, agents={unique_agents} - {reasoning}")
            return unique_agents, valid_steps

        except json.JSONDecodeError as e:
            logger.warning(f"Planner JSON parse error: {e}, response: {response[:200]}")
            agents = self._fallback_extraction(response)
            steps = [{"agents": agents, "goal": ""}] if agents else []
            return agents, steps

        except Exception as e:
            logger.error(f"Planner error: {e}")
            return [], []

    def _fallback_extraction(self, response: str) -> list[str]:
        """Fallback agent extraction when JSON parsing fails."""
        agents = []
        response_lower = response.lower()

        for agent_name in AGENT_CAPABILITIES.keys():
            if agent_name in response_lower:
                agents.append(agent_name)

        logger.info(f"Planner fallback extraction: {agents}")
        return agents


# Singleton
planner = Planner()
