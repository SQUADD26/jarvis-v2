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

AGENTI DISPONIBILI:
{agent_descriptions}

REGOLE:
1. Analizza cosa l'utente sta chiedendo, CONSIDERANDO IL CONTESTO della conversazione recente
2. Seleziona SOLO gli agenti necessari (può essere 0, 1, o più)
3. Se la richiesta è semplice conversazione (saluti, ringraziamenti, domande generiche su di te), non servono agenti
4. Se l'utente chiede qualcosa che richiede dati esterni (calendario, email, web), seleziona gli agenti appropriati
5. In caso di dubbio su calendario/email, è meglio includere l'agente che escluderlo
6. Se l'utente fa riferimento a qualcosa detto prima (es. "riprova", "fallo di nuovo", "continua"), USA IL CONTESTO per capire cosa intende

⚠️ REGOLA CRITICA - VERIFICA/CONTROLLA:
Quando l'utente chiede di VERIFICARE, CONTROLLARE, CONFERMARE qualcosa (calendario, email, ecc.),
DEVI SEMPRE attivare l'agente corrispondente per recuperare i dati REALI.
NON fidarti mai della conversazione precedente - l'utente vuole dati FRESCHI.

ESEMPI:
- "ciao come stai" → agents: []
- "cosa ho domani" → agents: ["calendar"]
- "mi passi l'agenda di lunedì" → agents: ["calendar"]
- "controlla l'agenda" → agents: ["calendar"]
- "verifica il calendario" → agents: ["calendar"]
- "è corretto?" (dopo aver parlato di calendario) → agents: ["calendar"]
- "controlla se è giusto" → agents: ["calendar"] (o l'agente del contesto)
- "crea una bozza email" → agents: ["email"]
- "controlla email e calendario" → agents: ["calendar", "email"]
- "che tempo fa a Milano" → agents: ["web"]
- "cerca nei miei documenti" → agents: ["rag"]
- "grazie mille" → agents: []
- "riprova" (dopo richiesta di ingestione URL) → agents: ["rag"]
- "fallo" (dopo richiesta di creare evento) → agents: ["calendar"]
- "chi e Marco Rossi?" → agents: ["kg"]
- "chi sono i miei colleghi?" → agents: ["kg"]
- "dimmi di piu su Acme" → agents: ["kg"]
- "per chi lavora Giovanni?" → agents: ["kg"]
- "quali persone conosco?" → agents: ["kg"]
- "chi e il mio capo?" → agents: ["kg"]
- "mostra le mie task" → agents: ["task"]
- "che task ho in scadenza?" → agents: ["task"]
- "crea task comprare latte" → agents: ["task"]
- "completa la task report" → agents: ["task"]
- "segna come fatta la task X" → agents: ["task"]

Rispondi SOLO con un JSON valido:
{{"agents": ["agent1", "agent2"], "reasoning": "breve spiegazione"}}

{conversation_context}
RICHIESTA UTENTE ATTUALE:
{user_input}

JSON:"""


class Planner:
    """LLM-based planner for determining required agents."""

    def __init__(self):
        self.model = "gemini-2.5-flash"

    async def plan(self, user_input: str, user_id: str = None, history: list = None) -> list[str]:
        """
        Analyze user input and determine which agents are needed.

        Args:
            user_input: The user's message
            user_id: User ID for logging
            history: Conversation history (list of HumanMessage/AIMessage)

        Returns:
            List of agent names to execute
        """
        # Build agent descriptions
        agent_descriptions = "\n".join([
            f"- {name}: {desc}" for name, desc in AGENT_CAPABILITIES.items()
        ])

        # Format conversation context (last 4 messages for context)
        conversation_context = ""
        if history and len(history) > 0:
            recent = history[-4:]  # Last 2 exchanges
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
            # Set user context for logging
            if user_id:
                gemini.set_user_context(user_id)

            response = await gemini.generate(
                prompt,
                model=self.model,
                temperature=0.1  # Low temperature for consistent decisions
            )

            # Parse JSON response
            clean_response = response.strip()
            if clean_response.startswith("```"):
                clean_response = clean_response.split("```")[1]
                if clean_response.startswith("json"):
                    clean_response = clean_response[4:]
                clean_response = clean_response.strip()

            result = json.loads(clean_response)
            agents = result.get("agents", [])
            reasoning = result.get("reasoning", "")

            # Validate agents
            valid_agents = [a for a in agents if a in AGENT_CAPABILITIES]

            logger.info(f"Planner decision: {valid_agents} - {reasoning}")
            return valid_agents

        except json.JSONDecodeError as e:
            logger.warning(f"Planner JSON parse error: {e}, response: {response[:200]}")
            # Fallback: try to extract agent names from response
            return self._fallback_extraction(response)

        except Exception as e:
            logger.error(f"Planner error: {e}")
            # On error, return empty (will use direct LLM response)
            return []

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
