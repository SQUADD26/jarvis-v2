"""Web agent - LLM-powered with tool calling."""

from typing import Any
import json
from jarvis.agents.base import BaseAgent
from jarvis.core.state import JarvisState
from jarvis.integrations.perplexity import perplexity
from jarvis.integrations.crawl4ai_client import crawler
from jarvis.integrations.gemini import gemini

# Tool definitions for the LLM
WEB_TOOLS = [
    {
        "name": "web_search",
        "description": "Cerca informazioni sul web usando Perplexity AI. Usa per domande su fatti, notizie, meteo, informazioni generali.",
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

AGENT_SYSTEM_PROMPT = """Sei un agente web. Il tuo compito è capire la richiesta dell'utente e chiamare il tool appropriato.

TOOL DISPONIBILI:
{tools}

REGOLE:
1. Analizza la richiesta e decidi quale tool usare
2. Per ricerche generali, domande, meteo, notizie → usa web_search
3. Se l'utente fornisce un URL specifico da leggere → usa scrape_url
4. Rispondi SOLO con un JSON valido nel formato:
   {{"tool": "nome_tool", "params": {{...parametri...}}}}

ESEMPI:
- "che tempo fa a Milano" → {{"tool": "web_search", "params": {{"query": "meteo Milano oggi"}}}}
- "ultime notizie su OpenAI" → {{"tool": "web_search", "params": {{"query": "ultime notizie OpenAI"}}}}
- "leggi questa pagina https://example.com/article" → {{"tool": "scrape_url", "params": {{"url": "https://example.com/article"}}}}
- "chi ha vinto le elezioni" → {{"tool": "web_search", "params": {{"query": "risultati elezioni recenti"}}}}

Rispondi SOLO con il JSON, nient'altro."""


class WebAgent(BaseAgent):
    name = "web"
    resource_type = "web"

    async def _execute(self, state: JarvisState) -> Any:
        """Execute web operations using LLM reasoning."""
        user_input = state["current_input"]

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
            tool_name = decision.get("tool")
            params = decision.get("params", {})

            self.logger.info(f"Web agent decision: {tool_name} with {params}")

        except Exception as e:
            self.logger.error(f"Failed to parse LLM response: {response[:200]}")
            return {"error": f"Non ho capito la richiesta: {str(e)}"}

        # Execute the tool
        return await self._execute_tool(tool_name, params)

    async def _execute_tool(self, tool_name: str, params: dict) -> dict:
        """Execute the selected tool with given parameters."""

        if tool_name == "web_search":
            return await self._tool_web_search(params)
        elif tool_name == "scrape_url":
            return await self._tool_scrape_url(params)
        else:
            return {"error": f"Tool sconosciuto: {tool_name}"}

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
