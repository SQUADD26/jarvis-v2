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
        "description": "Importa e indicizza una pagina web nella knowledge base. Usa quando l'utente vuole salvare/memorizzare un URL.",
        "parameters": {
            "url": "L'URL da importare",
            "doc_type": "Tipo documento: webpage, article, documentation (default: webpage)"
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
1. Per cercare informazioni → usa search_knowledge (ricerca ibrida semantica + keyword)
2. Per salvare una pagina web → usa ingest_url
3. Per salvare testo/note → usa ingest_text
4. Per vedere documenti disponibili → usa list_documents
5. Rispondi SOLO con JSON: {{"tool": "nome_tool", "params": {{...}}}}

ESEMPI:
- "cerca info sul progetto Alpha" → {{"tool": "search_knowledge", "params": {{"query": "progetto Alpha"}}}}
- "salva questa pagina https://..." → {{"tool": "ingest_url", "params": {{"url": "https://...", "doc_type": "webpage"}}}}
- "memorizza questa nota: ..." → {{"tool": "ingest_text", "params": {{"text": "...", "title": "Nota"}}}}
- "che documenti ho" → {{"tool": "list_documents", "params": {{"limit": 10}}}}

Rispondi SOLO con il JSON."""


class RAGAgent(BaseAgent):
    name = "rag"
    resource_type = "rag"

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
            doc_type = params.get("doc_type", "webpage")

            if not url:
                return {"error": "URL mancante"}

            result = await ingestion_pipeline.ingest_url(
                url=url,
                user_id=user_id,
                doc_type=doc_type
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
                doc_type="note"
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
