"""RAG agent - LLM-powered with hybrid search and reranking."""

from typing import Any
import json
from jarvis.agents.base import BaseAgent
from jarvis.core.state import JarvisState
from jarvis.integrations.gemini import gemini
from jarvis.rag.hybrid_search import hybrid_rag
from jarvis.rag.ingestion import ingestion_pipeline
from jarvis.db.repositories import RAGRepository

# Tool definitions for the LLM
RAG_TOOLS = [
    {
        "name": "search_knowledge",
        "description": "Cerca informazioni nella knowledge base usando ricerca ibrida (semantica + keyword) con reranking. Usa per domande su documenti caricati.",
        "parameters": {
            "query": "La query di ricerca"
        }
    },
    {
        "name": "ingest_url",
        "description": "Importa e indicizza una singola pagina web. Usa per pagine singole.",
        "parameters": {
            "url": "L'URL da importare",
            "title": "Titolo opzionale"
        }
    },
    {
        "name": "ingest_documentation",
        "description": "Importa una documentazione completa seguendo i link interni (deep crawling). Usa quando l'utente vuole salvare documentazione, guide multi-pagina, wiki, o siti con più pagine collegate.",
        "parameters": {
            "url": "L'URL iniziale della documentazione",
            "title": "Titolo della collezione",
            "max_pages": "Numero massimo di pagine da importare (default: 500)"
        }
    },
    {
        "name": "ingest_text",
        "description": "Salva del testo nella knowledge base. Usa quando l'utente vuole memorizzare note o informazioni testuali.",
        "parameters": {
            "text": "Il testo da salvare",
            "title": "Titolo del documento"
        }
    },
    {
        "name": "list_documents",
        "description": "Elenca i documenti nella knowledge base.",
        "parameters": {
            "limit": "Numero massimo di documenti (default: 10)"
        }
    }
]

AGENT_SYSTEM_PROMPT = """Sei un agente knowledge base con ricerca ibrida e reranking.

TOOL DISPONIBILI:
{tools}

REGOLE:
1. Per cercare informazioni → usa search_knowledge
2. Per salvare una SINGOLA pagina web → usa ingest_url
3. Per salvare DOCUMENTAZIONE MULTI-PAGINA (docs, guide, wiki) → usa ingest_documentation
4. Per salvare testo/note → usa ingest_text
5. Per vedere documenti disponibili → usa list_documents
6. Rispondi SOLO con JSON: {{"tool": "nome_tool", "params": {{...}}}}

ESEMPI:
- "cerca info sul progetto Alpha" → {{"tool": "search_knowledge", "params": {{"query": "progetto Alpha"}}}}
- "salva questa pagina https://..." → {{"tool": "ingest_url", "params": {{"url": "https://..."}}}}
- "importa la documentazione di https://docs.example.com" → {{"tool": "ingest_documentation", "params": {{"url": "https://docs.example.com", "title": "Example Docs", "max_pages": 500}}}}
- "ingerisci questo sito https://wiki.example.com" → {{"tool": "ingest_documentation", "params": {{"url": "https://wiki.example.com", "title": "Wiki", "max_pages": 500}}}}
- "memorizza questa nota: ..." → {{"tool": "ingest_text", "params": {{"text": "...", "title": "Nota"}}}}
- "che documenti ho" → {{"tool": "list_documents", "params": {{"limit": 10}}}}

Rispondi SOLO con il JSON."""


class RAGAgent(BaseAgent):
    name = "rag"
    resource_type = None  # No caching - RAG operations should always execute

    async def _execute(self, state: JarvisState) -> Any:
        """Execute RAG operations using LLM reasoning."""
        user_input = state["current_input"]
        user_id = state["user_id"]

        # Format tools for prompt
        tools_str = json.dumps(RAG_TOOLS, indent=2, ensure_ascii=False)
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

            self.logger.info(f"RAG agent decision: {tool_name} with {params}")

        except Exception as e:
            self.logger.error(f"Failed to parse LLM response: {response[:200]}")
            return {"error": f"Non ho capito la richiesta: {str(e)}"}

        # Execute the tool
        return await self._execute_tool(tool_name, params, user_id)

    async def _execute_tool(self, tool_name: str, params: dict, user_id: str) -> dict:
        """Execute the selected tool."""

        if tool_name == "search_knowledge":
            return await self._tool_search(params, user_id)
        elif tool_name == "ingest_url":
            return await self._tool_ingest_url(params, user_id)
        elif tool_name == "ingest_documentation":
            return await self._tool_ingest_documentation(params, user_id)
        elif tool_name == "ingest_text":
            return await self._tool_ingest_text(params, user_id)
        elif tool_name == "list_documents":
            return await self._tool_list_documents(params, user_id)
        else:
            return {"error": f"Tool sconosciuto: {tool_name}"}

    async def _tool_search(self, params: dict, user_id: str) -> dict:
        """Search using hybrid RAG with reranking."""
        try:
            query = params.get("query", "")

            result = await hybrid_rag.search_and_answer(
                query=query,
                user_id=user_id,
                limit=5
            )

            return {
                "operation": "search_knowledge",
                "query": query,
                "found": result["found"],
                "answer": result["answer"],
                "sources": result["sources"]
            }
        except Exception as e:
            self.logger.error(f"search_knowledge failed: {e}")
            return {"error": f"Errore nella ricerca: {str(e)}"}

    async def _tool_ingest_url(self, params: dict, user_id: str) -> dict:
        """Ingest a URL into the knowledge base."""
        try:
            url = params.get("url", "")
            title = params.get("title")

            if not url:
                return {"error": "URL mancante"}

            result = await ingestion_pipeline.ingest_url(
                url=url,
                user_id=user_id,
                title=title
            )

            if result["success"]:
                return {
                    "operation": "ingest_url",
                    "success": True,
                    "url": url,
                    "title": result.get("title"),
                    "chunks_count": result.get("chunks_count"),
                    "message": f"Pagina importata: {result.get('title')} ({result.get('chunks_count')} chunks)"
                }
            else:
                return {"error": result.get("error", "Errore nell'importazione")}

        except Exception as e:
            self.logger.error(f"ingest_url failed: {e}")
            return {"error": f"Errore nell'importazione: {str(e)}"}

    async def _tool_ingest_documentation(self, params: dict, user_id: str) -> dict:
        """Deep crawl and ingest documentation (multi-page)."""
        try:
            url = params.get("url", "")
            title = params.get("title")
            max_pages = params.get("max_pages", 500)

            if not url:
                return {"error": "URL mancante"}

            # Use deep ingestion
            result = await ingestion_pipeline.ingest_url_deep(
                url=url,
                user_id=user_id,
                title=title,
                max_depth=3,  # Deeper for large documentation sites
                max_pages=int(max_pages)
            )

            if result["success"]:
                return {
                    "operation": "ingest_documentation",
                    "success": True,
                    "url": url,
                    "title": result.get("title"),
                    "pages_ingested": result.get("pages_ingested"),
                    "total_pages_crawled": result.get("total_pages_crawled"),
                    "chunks_count": result.get("chunks_count"),
                    "message": f"Documentazione importata: {result.get('title')} - {result.get('pages_ingested')} pagine, {result.get('chunks_count')} chunks"
                }
            else:
                return {"error": result.get("error", "Errore nell'importazione")}

        except Exception as e:
            self.logger.error(f"ingest_documentation failed: {e}")
            return {"error": f"Errore nell'importazione: {str(e)}"}

    async def _tool_ingest_text(self, params: dict, user_id: str) -> dict:
        """Ingest text into the knowledge base."""
        try:
            text = params.get("text", "")
            title = params.get("title", "Nota")

            if not text:
                return {"error": "Testo mancante"}

            result = await ingestion_pipeline.ingest_text(
                text=text,
                user_id=user_id,
                title=title,
                source_type="note"
            )

            if result["success"]:
                return {
                    "operation": "ingest_text",
                    "success": True,
                    "title": title,
                    "chunks_count": result.get("chunks_count"),
                    "message": f"Testo salvato: {title}"
                }
            else:
                return {"error": result.get("error", "Errore nel salvataggio")}

        except Exception as e:
            self.logger.error(f"ingest_text failed: {e}")
            return {"error": f"Errore nel salvataggio: {str(e)}"}

    async def _tool_list_documents(self, params: dict, user_id: str) -> dict:
        """List documents in knowledge base."""
        try:
            limit = params.get("limit", 10)
            docs = await RAGRepository.list_documents(user_id=user_id, limit=limit)

            return {
                "operation": "list_documents",
                "documents": [
                    {
                        "id": d["id"],
                        "title": d["title"],
                        "source_url": d.get("source_url"),
                        "created_at": d.get("created_at")
                    }
                    for d in docs
                ],
                "count": len(docs)
            }
        except Exception as e:
            self.logger.error(f"list_documents failed: {e}")
            return {"error": f"Errore: {str(e)}"}


# Singleton
rag_agent = RAGAgent()
