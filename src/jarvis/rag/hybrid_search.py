"""Hybrid RAG search with reranking."""

from jarvis.integrations.gemini import gemini
from jarvis.integrations.reranker import reranker
from jarvis.db.supabase_client import get_db
from jarvis.utils.logging import get_logger

logger = get_logger(__name__)


class HybridRAG:
    """
    Hybrid RAG system combining:
    - Semantic search (vector similarity)
    - Keyword search (full-text)
    - Reranking for final ordering
    """

    def __init__(self):
        self.semantic_weight = 0.5
        self.keyword_weight = 0.5
        self.default_limit = 10
        self.rerank_top_k = 5

    async def search(
        self,
        query: str,
        user_id: str,
        limit: int = None,
        use_reranker: bool = True,
        semantic_threshold: float = 0.5
    ) -> list[dict]:
        """
        Perform hybrid search with optional reranking.

        Args:
            query: Search query
            user_id: User ID to search within
            limit: Max results to return
            use_reranker: Whether to use reranker for final ordering
            semantic_threshold: Minimum similarity threshold for semantic search

        Returns:
            List of documents sorted by relevance
        """
        limit = limit or self.default_limit

        # Run semantic and keyword search in parallel
        semantic_results, keyword_results = await self._parallel_search(
            query, user_id, limit * 2, semantic_threshold
        )

        # Merge and deduplicate results
        merged = self._merge_results(semantic_results, keyword_results)

        if not merged:
            return []

        # Rerank if enabled and we have results
        if use_reranker and len(merged) > 1:
            merged = await self._rerank_results(query, merged)

        # Return top results
        return merged[:limit]

    async def _parallel_search(
        self,
        query: str,
        user_id: str,
        limit: int,
        threshold: float
    ) -> tuple[list[dict], list[dict]]:
        """Run semantic and keyword search in parallel."""
        import asyncio

        # Generate query embedding
        query_embedding = await gemini.embed(query)

        # Run both searches
        semantic_task = self._semantic_search(query_embedding, user_id, limit, threshold)
        keyword_task = self._keyword_search(query, user_id, limit)

        semantic_results, keyword_results = await asyncio.gather(
            semantic_task, keyword_task
        )

        return semantic_results, keyword_results

    async def _semantic_search(
        self,
        query_embedding: list[float],
        user_id: str,
        limit: int,
        threshold: float
    ) -> list[dict]:
        """Perform semantic (vector) search."""
        db = get_db()

        try:
            result = db.rpc("match_rag_documents", {
                "query_embedding": query_embedding,
                "match_user_id": user_id,
                "match_threshold": threshold,
                "match_count": limit
            }).execute()

            docs = result.data if result.data else []

            # Add search type marker
            for doc in docs:
                doc["_search_type"] = "semantic"
                doc["_score"] = doc.get("similarity", 0)

            return docs

        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []

    async def _keyword_search(
        self,
        query: str,
        user_id: str,
        limit: int
    ) -> list[dict]:
        """Perform keyword (full-text) search."""
        db = get_db()

        try:
            # Use Supabase full-text search
            # This requires a text search column - fallback to ILIKE if not available
            result = db.table("rag_documents") \
                .select("id, title, content, metadata, source_url, chunk_index") \
                .eq("user_id", user_id) \
                .ilike("content", f"%{query}%") \
                .limit(limit) \
                .execute()

            docs = result.data if result.data else []

            # Add search type marker and calculate simple relevance score
            for doc in docs:
                doc["_search_type"] = "keyword"
                # Simple relevance: count query terms in content
                query_terms = query.lower().split()
                content_lower = doc["content"].lower()
                matches = sum(1 for term in query_terms if term in content_lower)
                doc["_score"] = matches / len(query_terms) if query_terms else 0

            return docs

        except Exception as e:
            logger.error(f"Keyword search failed: {e}")
            return []

    def _merge_results(
        self,
        semantic: list[dict],
        keyword: list[dict]
    ) -> list[dict]:
        """Merge and deduplicate results from both search types."""
        seen_ids = set()
        merged = []

        # Combine with weighted scores
        all_results = []

        for doc in semantic:
            doc["_final_score"] = doc["_score"] * self.semantic_weight
            all_results.append(doc)

        for doc in keyword:
            doc["_final_score"] = doc["_score"] * self.keyword_weight
            all_results.append(doc)

        # Sort by score and deduplicate
        all_results.sort(key=lambda x: x.get("_final_score", 0), reverse=True)

        for doc in all_results:
            doc_id = doc.get("id")
            if doc_id and doc_id not in seen_ids:
                seen_ids.add(doc_id)
                merged.append(doc)

        return merged

    async def _rerank_results(
        self,
        query: str,
        documents: list[dict]
    ) -> list[dict]:
        """Rerank documents using the reranker API."""
        if not documents:
            return []

        # Extract content for reranking
        contents = [doc["content"] for doc in documents]

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
                doc["_rerank_score"] = item["score"]
                doc["_final_score"] = item["score"]  # Replace with reranker score
                reordered.append(doc)

        return reordered

    async def search_and_answer(
        self,
        query: str,
        user_id: str,
        limit: int = 5
    ) -> dict:
        """
        Search and generate an answer using retrieved context.

        Args:
            query: User's question
            user_id: User ID
            limit: Max documents to use as context

        Returns:
            Dict with answer and sources
        """
        # Search
        docs = await self.search(query, user_id, limit=limit)

        if not docs:
            return {
                "answer": "Non ho trovato informazioni rilevanti nella knowledge base.",
                "sources": [],
                "found": False
            }

        # Build context
        context = "\n\n".join([
            f"[{doc.get('title', 'Untitled')}]\n{doc['content'][:2000]}"
            for doc in docs
        ])

        # Generate answer
        answer_prompt = f"""Basandoti SOLO sui seguenti documenti, rispondi alla domanda.
Se i documenti non contengono l'informazione richiesta, dillo chiaramente.
Non inventare informazioni non presenti nei documenti.

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
                    "score": round(doc.get("_final_score", 0), 3),
                    "source_url": doc.get("source_url")
                }
                for doc in docs
            ],
            "found": True
        }


# Singleton
hybrid_rag = HybridRAG()
