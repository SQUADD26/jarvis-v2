"""Hybrid RAG search with OpenAI embeddings and reranking."""

from jarvis.integrations.openai_embeddings import openai_embeddings
from jarvis.integrations.gemini import gemini
from jarvis.integrations.reranker import reranker
from jarvis.db.supabase_client import get_db
from jarvis.utils.logging import get_logger

logger = get_logger(__name__)


class HybridRAG:
    """
    Hybrid RAG system combining:
    - Semantic search (OpenAI 1536 dim vectors)
    - Full-text search (PostgreSQL tsvector)
    - Reranking for final ordering
    """

    def __init__(self):
        self.default_limit = 10
        self.rerank_candidates = 20  # Fetch more for reranking

    async def search(
        self,
        query: str,
        user_id: str,
        limit: int = None,
        use_reranker: bool = True,
        semantic_threshold: float = 0.4
    ) -> list[dict]:
        """
        Perform hybrid search with reranking.

        1. Generate query embedding (OpenAI)
        2. Call hybrid search RPC (semantic + full-text combined in PostgreSQL)
        3. Rerank results
        4. Return top-k
        """
        limit = limit or self.default_limit

        # Generate query embedding with OpenAI
        query_embedding = await openai_embeddings.embed(query)

        # Call hybrid search function in PostgreSQL
        db = get_db()
        try:
            result = db.rpc("search_rag_hybrid", {
                "query_embedding": query_embedding,
                "search_query": query,
                "match_user_id": user_id,
                "semantic_weight": 0.7,
                "fulltext_weight": 0.3,
                "match_threshold": semantic_threshold,
                "match_count": self.rerank_candidates if use_reranker else limit
            }).execute()

            docs = result.data if result.data else []

        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            # Fallback to semantic-only search
            docs = await self._semantic_search_fallback(query_embedding, user_id, limit, semantic_threshold)

        if not docs:
            return []

        # Rerank if enabled
        if use_reranker and len(docs) > 1:
            docs = await self._rerank_results(query, docs)

        return docs[:limit]

    async def search_semantic_only(
        self,
        query: str,
        user_id: str,
        limit: int = 10,
        threshold: float = 0.4
    ) -> list[dict]:
        """Semantic search only (no full-text, no reranking)."""
        query_embedding = await openai_embeddings.embed(query)

        db = get_db()
        try:
            result = db.rpc("match_rag_chunks", {
                "query_embedding": query_embedding,
                "match_user_id": user_id,
                "match_threshold": threshold,
                "match_count": limit
            }).execute()
            return result.data if result.data else []
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []

    async def search_fulltext_only(
        self,
        query: str,
        user_id: str,
        limit: int = 10
    ) -> list[dict]:
        """Full-text search only (no semantic, no reranking)."""
        db = get_db()
        try:
            result = db.rpc("search_rag_chunks_fulltext", {
                "search_query": query,
                "match_user_id": user_id,
                "match_count": limit
            }).execute()
            return result.data if result.data else []
        except Exception as e:
            logger.error(f"Full-text search failed: {e}")
            return []

    async def search_and_answer(
        self,
        query: str,
        user_id: str,
        limit: int = 5
    ) -> dict:
        """
        Search and generate an answer using retrieved context.
        """
        # Search with reranking
        docs = await self.search(query, user_id, limit=limit, use_reranker=True)

        if not docs:
            return {
                "answer": "Non ho trovato informazioni rilevanti nella knowledge base.",
                "sources": [],
                "found": False
            }

        # Build context from top results
        context_parts = []
        for doc in docs:
            title = doc.get("title", "Untitled")
            content = doc.get("content", "")[:2000]
            source_type = doc.get("source_type", "")
            context_parts.append(f"[{title}] ({source_type})\n{content}")

        context = "\n\n---\n\n".join(context_parts)

        # Generate answer
        answer_prompt = f"""Basandoti SOLO sui seguenti documenti, rispondi alla domanda.
Se i documenti non contengono l'informazione richiesta, dillo chiaramente.
Non inventare informazioni non presenti nei documenti.
Cita le fonti quando possibile.

DOCUMENTI:
{context}

DOMANDA: {query}

RISPOSTA:"""

        answer = await gemini.generate(
            answer_prompt,
            model="gemini-2.5-flash",
            temperature=0.3
        )

        return {
            "answer": answer,
            "sources": [
                {
                    "title": doc.get("title"),
                    "source_type": doc.get("source_type"),
                    "source_url": doc.get("source_url"),
                    "score": round(doc.get("combined_score", doc.get("similarity", 0)), 3)
                }
                for doc in docs
            ],
            "found": True
        }

    async def _semantic_search_fallback(
        self,
        query_embedding: list[float],
        user_id: str,
        limit: int,
        threshold: float
    ) -> list[dict]:
        """Fallback to semantic-only search if hybrid fails."""
        db = get_db()
        try:
            result = db.rpc("match_rag_chunks", {
                "query_embedding": query_embedding,
                "match_user_id": user_id,
                "match_threshold": threshold,
                "match_count": limit
            }).execute()
            return result.data if result.data else []
        except Exception as e:
            logger.error(f"Semantic fallback also failed: {e}")
            return []

    async def _rerank_results(
        self,
        query: str,
        documents: list[dict]
    ) -> list[dict]:
        """Rerank documents using the reranker API."""
        if not documents:
            return []

        # Extract content for reranking
        contents = [doc.get("content", "")[:1000] for doc in documents]

        # Call reranker
        reranked = await reranker.rerank(
            query=query,
            documents=contents,
            top_k=len(documents)
        )

        # Reorder documents based on reranker scores
        reordered = []
        for item in reranked:
            idx = item["index"]
            if idx < len(documents):
                doc = documents[idx].copy()
                doc["rerank_score"] = item["score"]
                reordered.append(doc)

        return reordered


# Singleton
hybrid_rag = HybridRAG()
