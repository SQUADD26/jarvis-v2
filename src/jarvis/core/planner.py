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
    "rag": "Knowledge base personale: cercare nei documenti dell'utente, file caricati, note"
}

PLANNER_PROMPT = """Sei un planner che decide quali agenti attivare per rispondere alla richiesta dell'utente.

AGENTI DISPONIBILI:
{agent_descriptions}

REGOLE:
1. Analizza cosa l'utente sta chiedendo
2. Seleziona SOLO gli agenti necessari (può essere 0, 1, o più)
3. Se la richiesta è semplice conversazione (saluti, ringraziamenti, domande generiche su di te), non servono agenti
4. Se l'utente chiede qualcosa che richiede dati esterni (calendario, email, web), seleziona gli agenti appropriati
5. In caso di dubbio su calendario/email, è meglio includere l'agente che escluderlo

ESEMPI:
- "ciao come stai" → agents: []
- "cosa ho domani" → agents: ["calendar"]
- "mi passi l'agenda di lunedì" → agents: ["calendar"]
- "crea una bozza email" → agents: ["email"]
- "controlla email e calendario" → agents: ["calendar", "email"]
- "che tempo fa a Milano" → agents: ["web"]
- "cerca nei miei documenti" → agents: ["rag"]
- "grazie mille" → agents: []

Rispondi SOLO con un JSON valido:
{{"agents": ["agent1", "agent2"], "reasoning": "breve spiegazione"}}

RICHIESTA UTENTE:
{user_input}

JSON:"""


class Planner:
    """LLM-based planner for determining required agents."""

    def __init__(self):
        self.model = "gemini-2.5-flash"

    async def plan(self, user_input: str, user_id: str = None) -> list[str]:
        """
        Analyze user input and determine which agents are needed.

        Args:
            user_input: The user's message
            user_id: User ID for logging

        Returns:
            List of agent names to execute
        """
        # Build agent descriptions
        agent_descriptions = "\n".join([
            f"- {name}: {desc}" for name, desc in AGENT_CAPABILITIES.items()
        ])

        prompt = PLANNER_PROMPT.format(
            agent_descriptions=agent_descriptions,
            user_input=user_input
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
