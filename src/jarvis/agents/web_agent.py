from typing import Any
import hashlib
import re
from jarvis.agents.base import BaseAgent
from jarvis.core.state import JarvisState
from jarvis.core.freshness import freshness
from jarvis.integrations.perplexity import perplexity
from jarvis.integrations.crawl4ai_client import crawler


class WebAgent(BaseAgent):
    name = "web"
    resource_type = "web"

    async def _execute(self, state: JarvisState) -> Any:
        """Execute web operations based on intent."""
        intent = state["intent"]
        user_input = state["current_input"]

        if intent == "web_search":
            return await self._handle_search(user_input, state["user_id"])
        elif intent == "web_scrape":
            return await self._handle_scrape(user_input)
        else:
            return await self._handle_search(user_input, state["user_id"])

    async def _handle_search(self, query: str, user_id: str) -> dict:
        """Handle web search with Perplexity."""
        # Check cache first (web searches can be cached longer)
        query_hash = hashlib.md5(query.encode()).hexdigest()

        cached = await freshness.get_cached("web", user_id, query_hash)
        if cached:
            self.logger.debug(f"Using cached search for: {query[:30]}...")
            return cached

        # Perform search
        result = await perplexity.search(query)

        search_result = {
            "operation": "search",
            "query": query,
            "answer": result["answer"],
            "citations": result.get("citations", []),
            "related_questions": result.get("related_questions", [])
        }

        # Cache result
        await freshness.set_cache("web", user_id, search_result, query_hash)

        return search_result

    async def _handle_scrape(self, query: str) -> dict:
        """Handle web scraping with Crawl4AI."""
        # Extract URL from query
        url_pattern = r'https?://[^\s]+'
        urls = re.findall(url_pattern, query)

        if not urls:
            return {
                "operation": "error",
                "message": "Non ho trovato un URL valido nella richiesta"
            }

        url = urls[0]

        # Scrape the URL
        result = await crawler.scrape_url(url)

        if not result["success"]:
            return {
                "operation": "error",
                "message": f"Non sono riuscito a leggere la pagina: {url}"
            }

        return {
            "operation": "scrape",
            "url": url,
            "title": result["title"],
            "content": result["content"][:5000],  # Limit content size
            "links": result["links"]
        }


# Singleton
web_agent = WebAgent()
