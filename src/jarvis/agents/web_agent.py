"""Web agent - LLM-powered with tool calling."""

from typing import Any
import json
import asyncio
from jarvis.agents.base import BaseAgent
from jarvis.core.state import JarvisState
from jarvis.integrations.perplexity import perplexity
from jarvis.integrations.apify_google import apify_google
from jarvis.integrations.crawl4ai_client import crawler
from jarvis.integrations.gemini import gemini

# Tool definitions for the LLM
WEB_TOOLS = [
    {
        "name": "google_search",
        "description": "Cerca su Google. PREFERISCI QUESTO per: orari di apertura, luoghi vicini, attività commerciali, ristoranti, bar, negozi, informazioni locali specifiche.",
        "parameters": {
            "query": "La query di ricerca (es. 'bar vicino a Milano centro', 'orari apertura Esselunga Torino')"
        }
    },
    {
        "name": "web_search",
        "description": "Cerca informazioni generali usando Perplexity AI. Usa per: notizie, fatti, ricerche approfondite, domande generiche.",
        "parameters": {
            "query": "La query di ricerca in linguaggio naturale"
        }
    },
    {
        "name": "scrape_url",
        "description": "Legge e estrae il contenuto di una pagina web specifica. Usa quando l'utente fornisce un URL.",
        "parameters": {
            "url": "L'URL completo della pagina da leggere"
        }
    }
]

AGENT_SYSTEM_PROMPT = """Sei un agente web. Il tuo compito è capire la richiesta dell'utente e chiamare i tool appropriati.

TOOL DISPONIBILI:
{tools}

🎯 QUANDO USARE QUALE TOOL:
- google_search → orari apertura, luoghi/attività vicine, bar/ristoranti, negozi, info locali specifiche
- web_search → notizie, fatti generali, ricerche approfondite, domande generiche
- scrape_url → quando l'utente fornisce un URL specifico

REGOLE:
1. Analizza la richiesta e decidi quali tool usare
2. PREFERISCI google_search per query locali/specifiche (orari, luoghi, attività)
3. Usa web_search per ricerche generali e notizie
4. Se la richiesta contiene MULTIPLE OPERAZIONI, restituisci una LISTA di tool calls
5. Rispondi SOLO con un JSON valido

ESEMPI:
- "a che ora apre il Bar Mario" → {{"tool": "google_search", "params": {{"query": "Bar Mario orari apertura"}}}}
- "bar buoni vicino a me" → {{"tool": "google_search", "params": {{"query": "bar migliori vicino a me"}}}}
- "ristoranti Milano centro" → {{"tool": "google_search", "params": {{"query": "ristoranti Milano centro"}}}}
- "ultime notizie su OpenAI" → {{"tool": "web_search", "params": {{"query": "ultime notizie OpenAI"}}}}
- "che tempo fa a Milano" → {{"tool": "google_search", "params": {{"query": "meteo Milano oggi"}}}}
- "leggi https://example.com" → {{"tool": "scrape_url", "params": {{"url": "https://example.com"}}}}

Rispondi SOLO con il JSON, nient'altro."""


class WebAgent(BaseAgent):
    name = "web"
    resource_type = None  # No caching - web operations should always execute fresh

    async def _execute(self, state: JarvisState) -> Any:
        """Execute web operations using LLM reasoning."""
        user_input = state.get("enriched_input", state["current_input"])

        # Format tools for prompt
        tools_str = json.dumps(WEB_TOOLS, indent=2, ensure_ascii=False)

        # Build prompt
        prompt = AGENT_SYSTEM_PROMPT.format(tools=tools_str)

        # Ask LLM what to do
        response = await gemini.generate(
            user_input,
            system_instruction=prompt,
            model="gemini-2.5-flash",
            temperature=0.1
        )

        # Parse LLM response
        try:
            clean_response = response.strip()
            if clean_response.startswith("```"):
                clean_response = clean_response.split("```")[1]
                if clean_response.startswith("json"):
                    clean_response = clean_response[4:]
                clean_response = clean_response.strip()

            decision = json.loads(clean_response)

            # Handle both single and multiple tool calls
            if isinstance(decision, list):
                # Multiple tool calls - execute in parallel
                self.logger.info(f"Web agent: {len(decision)} tool calls to execute")
                tasks = []
                for call in decision:
                    tool_name = call.get("tool")
                    params = call.get("params", {})
                    self.logger.info(f"Web agent decision: {tool_name} with {params}")
                    tasks.append(self._execute_tool(tool_name, params))

                results = await asyncio.gather(*tasks, return_exceptions=True)
                # Convert exceptions to error dicts
                processed_results = []
                for r in results:
                    if isinstance(r, Exception):
                        processed_results.append({"error": str(r)})
                    else:
                        processed_results.append(r)
                return {"multiple_results": processed_results}
            else:
                # Single tool call
                tool_name = decision.get("tool")
                params = decision.get("params", {})
                self.logger.info(f"Web agent decision: {tool_name} with {params}")
                return await self._execute_tool(tool_name, params)

        except Exception as e:
            self.logger.error(f"Failed to parse LLM response: {response[:200]}")
            return {"error": f"Non ho capito la richiesta: {str(e)}"}

    async def _execute_tool(self, tool_name: str, params: dict) -> dict:
        """Execute the selected tool with given parameters."""

        if tool_name == "google_search":
            return await self._tool_google_search(params)
        elif tool_name == "web_search":
            return await self._tool_web_search(params)
        elif tool_name == "scrape_url":
            return await self._tool_scrape_url(params)
        else:
            return {"error": f"Tool sconosciuto: {tool_name}"}

    async def _tool_google_search(self, params: dict) -> dict:
        """Search Google using Apify - better for local/specific queries."""
        try:
            query = params.get("query", "")

            result = await apify_google.search(query)

            if "error" in result:
                # Fallback to Perplexity if Apify fails
                self.logger.warning(f"Apify failed, falling back to Perplexity: {result['error']}")
                return await self._tool_web_search(params)

            # Format results for response
            formatted = apify_google.format_results(result)

            return {
                "operation": "google_search",
                "query": query,
                "results": result.get("results", []),
                "formatted": formatted,
                "total": result.get("total_results", 0)
            }
        except Exception as e:
            self.logger.error(f"google_search failed: {e}")
            # Fallback to Perplexity
            return await self._tool_web_search(params)

    async def _tool_web_search(self, params: dict) -> dict:
        """Search the web using Perplexity."""
        try:
            query = params.get("query", "")

            result = await perplexity.search(query)

            return {
                "operation": "web_search",
                "query": query,
                "answer": result["answer"],
                "citations": result.get("citations", [])[:5],
                "related_questions": result.get("related_questions", [])[:3]
            }
        except Exception as e:
            self.logger.error(f"web_search failed: {e}")
            return {"error": f"Errore nella ricerca: {str(e)}"}

    async def _tool_scrape_url(self, params: dict) -> dict:
        """Scrape a URL using Crawl4AI."""
        try:
            url = params.get("url", "")

            if not url:
                return {"error": "URL mancante"}

            result = await crawler.scrape_url(url)

            if not result["success"]:
                return {"error": f"Non sono riuscito a leggere la pagina: {url}"}

            return {
                "operation": "scrape_url",
                "url": url,
                "title": result["title"],
                "content": result["content"][:5000],  # Limit content
                "links": result["links"][:5]
            }
        except Exception as e:
            self.logger.error(f"scrape_url failed: {e}")
            return {"error": f"Errore nello scraping: {str(e)}"}


# Singleton
web_agent = WebAgent()
