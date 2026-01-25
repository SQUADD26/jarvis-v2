from typing import Any
from jarvis.agents.base import BaseAgent
from jarvis.core.state import JarvisState
from jarvis.integrations.gemini import gemini
from jarvis.db.repositories import RAGRepository


class RAGAgent(BaseAgent):
    name = "rag"
    resource_type = "rag"

    async def _execute(self, state: JarvisState) -> Any:
        """Execute RAG operations."""
        intent = state["intent"]
        user_input = state["current_input"]
        user_id = state["user_id"]

        if intent == "rag_query":
            return await self._handle_query(user_input, user_id)
        elif intent == "rag_ingest":
            return await self._handle_ingest(user_input, user_id)
        else:
            return await self._handle_query(user_input, user_id)

    async def _handle_query(self, query: str, user_id: str) -> dict:
        """Query the RAG knowledge base."""
        # Generate query embedding
        query_embedding = await gemini.embed(query)

        # Search documents
        docs = await RAGRepository.search_documents(
            user_id=user_id,
            query_embedding=query_embedding,
            threshold=0.6,
            limit=5
        )

        if not docs:
            return {
                "operation": "query",
                "found": False,
                "message": "Non ho trovato documenti rilevanti nel knowledge base"
            }

        # Build context from docs
        context = "\n\n".join([
            f"[{d['title']}]\n{d['content']}"
            for d in docs
        ])

        # Generate answer using context
        answer_prompt = f"""Basandoti sui seguenti documenti, rispondi alla domanda.
Se i documenti non contengono l'informazione, dillo chiaramente.

DOCUMENTI:
{context}

DOMANDA: {query}

RISPOSTA:"""

        answer = await gemini.generate(answer_prompt, temperature=0.5)

        return {
            "operation": "query",
            "found": True,
            "answer": answer,
            "sources": [{"title": d["title"], "similarity": d["similarity"]} for d in docs]
        }

    async def _handle_ingest(self, content: str, user_id: str) -> dict:
        """Ingest new document into knowledge base."""
        # For now, simple ingestion
        # TODO: Add chunking for long documents

        # Extract title from first line or generate
        lines = content.strip().split("\n")
        title = lines[0][:100] if lines else "Untitled"

        # Generate embedding
        embedding = await gemini.embed(content[:8000])  # Limit for embedding

        # Save to DB
        doc = await RAGRepository.save_document(
            user_id=user_id,
            title=title,
            content=content,
            embedding=embedding
        )

        return {
            "operation": "ingest",
            "success": True,
            "document_id": doc["id"] if doc else None,
            "title": title
        }


# Singleton
rag_agent = RAGAgent()
