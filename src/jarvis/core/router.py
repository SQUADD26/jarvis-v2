import numpy as np
from typing import Tuple
from jarvis.integrations.gemini import gemini
from jarvis.core.state import INTENT_CATEGORIES
from jarvis.utils.logging import get_logger

logger = get_logger(__name__)


class SemanticRouter:
    """Fast semantic routing to bypass LLM for simple intents."""

    # Example queries for each intent (used for embedding similarity)
    INTENT_EXAMPLES = {
        "calendar_read": [
            "dammi gli eventi",
            "eventi di lunedì",
            "cosa ho lunedì",
            "appuntamenti per lunedì",
            "agenda della settimana",
            "calendario di domani",
            "che impegni ho oggi",
            "mostrami il calendario",
            "cosa ho in agenda domani",
            "quali sono i miei appuntamenti",
            "ho riunioni questa settimana"
        ],
        "calendar_write": [
            "crea un evento",
            "aggiungi un appuntamento",
            "schedula una riunione",
            "sposta l'evento",
            "cancella l'appuntamento"
        ],
        "email_read": [
            "controlla le email",
            "ho messaggi nuovi",
            "mostrami la posta",
            "leggi le email",
            "ci sono email importanti"
        ],
        "email_write": [
            "scrivi una email",
            "manda un messaggio a",
            "rispondi all'email",
            "invia una mail",
            "componi un'email"
        ],
        "web_search": [
            "che tempo fa",
            "meteo oggi",
            "previsioni meteo",
            "temperatura a",
            "piove oggi",
            "cerca su internet",
            "cerca informazioni su",
            "cosa sai di",
            "trova notizie su",
            "ricerca web",
            "cerca online"
        ],
        "web_scrape": [
            "leggi questa pagina",
            "estrai contenuto da",
            "scrape questo url",
            "analizza questo sito"
        ],
        "rag_query": [
            "cerca nei miei documenti",
            "cosa c'è nei file",
            "trova nel knowledge base"
        ],
        "chitchat": [
            "ciao",
            "come stai",
            "grazie",
            "buongiorno",
            "ok perfetto"
        ]
    }

    def __init__(self):
        self._intent_embeddings: dict[str, list[list[float]]] = {}
        self._initialized = False

    async def initialize(self):
        """Pre-compute embeddings for all intent examples."""
        if self._initialized:
            return

        logger.info("Initializing semantic router...")

        for intent, examples in self.INTENT_EXAMPLES.items():
            embeddings = await gemini.embed_batch(examples)
            self._intent_embeddings[intent] = embeddings

        self._initialized = True
        logger.info("Semantic router initialized")

    async def route(self, query: str, threshold: float = 0.75) -> Tuple[str, float]:
        """
        Route query to intent based on semantic similarity.
        Returns (intent, confidence).
        """
        if not self._initialized:
            await self.initialize()

        # Get embedding for query
        query_embedding = await gemini.embed(query)
        query_vec = np.array(query_embedding)

        best_intent = "unknown"
        best_score = 0.0

        for intent, embeddings in self._intent_embeddings.items():
            # Compute similarity with all examples for this intent
            similarities = []
            for emb in embeddings:
                emb_vec = np.array(emb)
                # Cosine similarity
                sim = np.dot(query_vec, emb_vec) / (
                    np.linalg.norm(query_vec) * np.linalg.norm(emb_vec)
                )
                similarities.append(sim)

            # Take max similarity
            max_sim = max(similarities)

            if max_sim > best_score:
                best_score = max_sim
                best_intent = intent

        # If below threshold, mark as complex (needs full LLM)
        if best_score < threshold:
            return "complex", best_score

        logger.debug(f"Routed '{query[:50]}...' to '{best_intent}' (score={best_score:.3f})")
        return best_intent, best_score

    def get_required_agents(self, intent: str) -> list[str]:
        """Get list of agents needed for an intent."""
        return INTENT_CATEGORIES.get(intent, [])


# Singleton
router = SemanticRouter()
