"""RAG agent - LLM-powered with tool calling."""

from typing import Any
import json
from jarvis.agents.base import BaseAgent
from jarvis.core.state import JarvisState
from jarvis.integrations.gemini import gemini
from jarvis.db.repositories import RAGRepository

# Tool definitions for the LLM
RAG_TOOLS = [
    {
        "name": "search_knowledge",
        "description": "Cerca informazioni nella knowledge base personale dell'utente. Usa per domande su documenti caricati, note, file personali.",
        "parameters": {
            "query": "La query di ricerca per trovare documenti rilevanti"
        }
    },
    {
        "name": "list_documents",
        "description": "Elenca i documenti disponibili nella knowledge base.",
        "parameters": {
            "limit": "Numero massimo di documenti da mostrare (default: 10)"
        }
    }
]

AGENT_SYSTEM_PROMPT = """Sei un agente knowledge base. Il tuo compito è capire la richiesta dell'utente e cercare nei suoi documenti personali.

TOOL DISPONIBILI:
{tools}

REGOLE:
1. Analizza la richiesta e decidi quale tool usare
2. Per cercare informazioni specifiche → usa search_knowledge
3. Per vedere quali documenti sono disponibili → usa list_documents
4. Rispondi SOLO con un JSON valido nel formato:
   {{"tool": "nome_tool", "params": {{...parametri...}}}}

ESEMPI:
- "cosa c'è nei miei documenti sul progetto X" → {{"tool": "search_knowledge", "params": {{"query": "progetto X"}}}}
- "cerca informazioni sul budget" → {{"tool": "search_knowledge", "params": {{"query": "budget"}}}}
- "quali documenti ho caricato" → {{"tool": "list_documents", "params": {{"limit": 10}}}}
- "cosa dice la mia nota sulla riunione" → {{"tool": "search_knowledge", "params": {{"query": "nota riunione"}}}}

Rispondi SOLO con il JSON, nient'altro."""


class RAGAgent(BaseAgent):
    name = "rag"
    resource_type = "rag"

    async def _execute(self, state: JarvisState) -> Any:
        """Execute RAG operations using LLM reasoning."""
        user_input = state["current_input"]
        user_id = state["user_id"]

        # Format tools for prompt
        tools_str = json.dumps(RAG_TOOLS, indent=2, ensure_ascii=False)

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

            self.logger.info(f"RAG agent decision: {tool_name} with {params}")

        except Exception as e:
            self.logger.error(f"Failed to parse LLM response: {response[:200]}")
            return {"error": f"Non ho capito la richiesta: {str(e)}"}

        # Execute the tool
        return await self._execute_tool(tool_name, params, user_id)

    async def _execute_tool(self, tool_name: str, params: dict, user_id: str) -> dict:
        """Execute the selected tool with given parameters."""

        if tool_name == "search_knowledge":
            return await self._tool_search_knowledge(params, user_id)
        elif tool_name == "list_documents":
            return await self._tool_list_documents(params, user_id)
        else:
            return {"error": f"Tool sconosciuto: {tool_name}"}

    async def _tool_search_knowledge(self, params: dict, user_id: str) -> dict:
        """Search the knowledge base."""
        try:
            query = params.get("query", "")

            # Generate query embedding
            query_embedding = await gemini.embed(query)

            # Search documents
            docs = await RAGRepository.search_documents(
                user_id=user_id,
                query_embedding=query_embedding,
                threshold=0.5,
                limit=5
            )

            if not docs:
                return {
                    "operation": "search_knowledge",
                    "query": query,
                    "found": False,
                    "message": "Non ho trovato documenti rilevanti"
                }

            # Build context from docs
            context = "\n\n".join([
                f"[{d['title']}]\n{d['content'][:2000]}"
                for d in docs
            ])

            # Generate answer using context
            answer_prompt = f"""Basandoti sui seguenti documenti, rispondi alla domanda.
Se i documenti non contengono l'informazione, dillo chiaramente.

DOCUMENTI:
{context}

DOMANDA: {query}

RISPOSTA:"""

            answer = await gemini.generate(
                answer_prompt,
                model="gemini-2.5-flash",
                temperature=0.5
            )

            return {
                "operation": "search_knowledge",
                "query": query,
                "found": True,
                "answer": answer,
                "sources": [
                    {"title": d["title"], "similarity": round(d["similarity"], 2)}
                    for d in docs
                ]
            }
        except Exception as e:
            self.logger.error(f"search_knowledge failed: {e}")
            return {"error": f"Errore nella ricerca: {str(e)}"}

    async def _tool_list_documents(self, params: dict, user_id: str) -> dict:
        """List documents in knowledge base."""
        try:
            limit = params.get("limit", 10)

            docs = await RAGRepository.list_documents(user_id=user_id, limit=limit)

            return {
                "operation": "list_documents",
                "documents": [
                    {"id": d["id"], "title": d["title"], "created_at": d.get("created_at")}
                    for d in docs
                ],
                "count": len(docs)
            }
        except Exception as e:
            self.logger.error(f"list_documents failed: {e}")
            return {"error": f"Errore nel listare documenti: {str(e)}"}


# Singleton
rag_agent = RAGAgent()
