"""Reranker API client."""

import httpx
from jarvis.utils.logging import get_logger

logger = get_logger(__name__)

RERANKER_BASE_URL = "https://reranker.srv938822.hstgr.cloud"


class RerankerClient:
    """Client for the reranker API."""

    def __init__(self):
        self.base_url = RERANKER_BASE_URL
        self.timeout = 30.0

    async def health_check(self) -> bool:
        """Check if reranker API is healthy."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Reranker health check failed: {e}")
            return False

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int = None
    ) -> list[dict]:
        """
        Rerank documents based on relevance to query.

        Args:
            query: The search query
            documents: List of document texts to rerank
            top_k: Optional limit on number of results

        Returns:
            List of dicts with 'index', 'score', 'text' sorted by relevance
        """
        if not documents:
            return []

        payload = {
            "query": query,
            "documents": documents
        }
        if top_k:
            payload["top_k"] = top_k

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/rerank",
                    json=payload
                )
                response.raise_for_status()
                data = response.json()

                # Return results with original text attached
                results = []
                for item in data.get("results", []):
                    idx = item.get("index", 0)
                    results.append({
                        "index": idx,
                        "score": item.get("score", 0.0),
                        "text": documents[idx] if idx < len(documents) else ""
                    })

                return results

        except Exception as e:
            logger.error(f"Reranker failed: {e}")
            # Fallback: return documents in original order with dummy scores
            return [
                {"index": i, "score": 1.0 - (i * 0.1), "text": doc}
                for i, doc in enumerate(documents)
            ]


# Singleton
reranker = RerankerClient()
