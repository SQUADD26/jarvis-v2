"""Apify Google Search Scraper client for local/specific queries."""

import httpx
from typing import Optional
from jarvis.config import get_settings
from jarvis.utils.logging import get_logger

logger = get_logger(__name__)


class ApifyGoogleClient:
    """Client for Apify Google Search Scraper - better for local queries."""

    def __init__(self):
        settings = get_settings()
        self.api_key = settings.apify_api_key
        self.base_url = "https://api.apify.com/v2/acts/apify~google-search-scraper"

    async def search(
        self,
        query: str,
        max_results: int = 10,
        language: str = "it",
        country: str = "IT"
    ) -> dict:
        """
        Search Google using Apify scraper.
        Better for: opening hours, nearby places, specific local info.
        """
        if not self.api_key:
            return {"error": "Apify API key not configured"}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/run-sync-get-dataset-items",
                    params={"token": self.api_key},
                    json={
                        "queries": query,
                        "maxPagesPerQuery": 1,
                        "resultsPerPage": max_results,
                        "languageCode": language,
                        "countryCode": country,
                        "mobileResults": False,
                        "includeUnfilteredResults": False
                    },
                    timeout=60.0  # Apify can be slow
                )

                response.raise_for_status()
                data = response.json()

                # Parse results
                results = []
                for item in data:
                    # Organic results
                    for organic in item.get("organicResults", []):
                        results.append({
                            "type": "organic",
                            "title": organic.get("title", ""),
                            "url": organic.get("url", ""),
                            "description": organic.get("description", ""),
                            "position": organic.get("position", 0)
                        })

                    # Knowledge panel (useful for opening hours, info)
                    knowledge = item.get("knowledgePanel", {})
                    if knowledge:
                        results.append({
                            "type": "knowledge_panel",
                            "title": knowledge.get("title", ""),
                            "description": knowledge.get("description", ""),
                            "info": knowledge.get("info", {}),
                            "attributes": knowledge.get("attributes", [])
                        })

                    # Local results (maps, places)
                    for local in item.get("localResults", []):
                        results.append({
                            "type": "local",
                            "title": local.get("title", ""),
                            "address": local.get("address", ""),
                            "rating": local.get("rating"),
                            "reviews": local.get("reviewsCount"),
                            "phone": local.get("phone", ""),
                            "website": local.get("website", ""),
                            "hours": local.get("openingHours", "")
                        })

                    # People Also Ask
                    for paa in item.get("peopleAlsoAsk", []):
                        results.append({
                            "type": "people_also_ask",
                            "question": paa.get("question", ""),
                            "answer": paa.get("answer", "")
                        })

                return {
                    "query": query,
                    "results": results[:max_results],
                    "total_results": len(results)
                }

            except httpx.TimeoutException:
                logger.error(f"Apify search timeout for: {query}")
                return {"error": "Timeout nella ricerca Google"}
            except Exception as e:
                logger.error(f"Apify search failed: {e}")
                return {"error": f"Errore nella ricerca: {str(e)}"}

    def format_results(self, search_result: dict) -> str:
        """Format search results for LLM consumption."""
        if "error" in search_result:
            return f"Errore: {search_result['error']}"

        results = search_result.get("results", [])
        if not results:
            return "Nessun risultato trovato."

        formatted = []
        for r in results:
            if r["type"] == "knowledge_panel":
                formatted.append(f"📋 {r['title']}: {r['description']}")
                if r.get("attributes"):
                    for attr in r["attributes"][:5]:
                        formatted.append(f"   • {attr}")

            elif r["type"] == "local":
                line = f"📍 {r['title']}"
                if r.get("rating"):
                    line += f" ⭐{r['rating']}"
                if r.get("address"):
                    line += f" - {r['address']}"
                if r.get("hours"):
                    line += f"\n   🕐 {r['hours']}"
                if r.get("phone"):
                    line += f"\n   📞 {r['phone']}"
                formatted.append(line)

            elif r["type"] == "organic":
                formatted.append(f"🔗 {r['title']}\n   {r['description'][:200]}")

            elif r["type"] == "people_also_ask":
                formatted.append(f"❓ {r['question']}\n   {r['answer'][:200]}")

        return "\n\n".join(formatted[:8])


# Singleton
apify_google = ApifyGoogleClient()
