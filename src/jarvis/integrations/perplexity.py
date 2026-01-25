import httpx
from typing import Optional
from jarvis.config import get_settings
from jarvis.utils.logging import get_logger

logger = get_logger(__name__)


class PerplexityClient:
    def __init__(self):
        settings = get_settings()
        self.api_key = settings.perplexity_api_key
        self.base_url = "https://api.perplexity.ai"

    async def search(
        self,
        query: str,
        model: str = "llama-3.1-sonar-small-128k-online",
        max_tokens: int = 1024
    ) -> dict:
        """Search the web using Perplexity."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "Sei un assistente di ricerca. Fornisci risposte accurate e concise basate sulle informazioni web più recenti."
                        },
                        {
                            "role": "user",
                            "content": query
                        }
                    ],
                    "max_tokens": max_tokens,
                    "return_citations": True,
                    "return_related_questions": True
                },
                timeout=30.0
            )

            response.raise_for_status()
            data = response.json()

            return {
                "answer": data["choices"][0]["message"]["content"],
                "citations": data.get("citations", []),
                "related_questions": data.get("related_questions", [])
            }

    async def research(
        self,
        topic: str,
        depth: str = "normal"  # "quick", "normal", "deep"
    ) -> dict:
        """Perform deeper research on a topic."""
        prompts = {
            "quick": f"Dammi una breve panoramica su: {topic}",
            "normal": f"Fammi una ricerca approfondita su: {topic}. Includi fatti chiave, numeri e fonti.",
            "deep": f"Analizza in modo esaustivo: {topic}. Voglio tutti i dettagli, diverse prospettive, dati recenti e fonti affidabili."
        }

        return await self.search(prompts.get(depth, prompts["normal"]))


# Singleton
perplexity = PerplexityClient()
