"""OpenAI Embeddings client - text-embedding-3-large (3072 dim)."""

import httpx
from jarvis.config import get_settings
from jarvis.utils.logging import get_logger

logger = get_logger(__name__)

OPENAI_EMBEDDING_MODEL = "text-embedding-3-large"
OPENAI_EMBEDDING_DIM = 3072  # Full dimensions, using halfvec for HNSW compatibility
OPENAI_API_URL = "https://api.openai.com/v1/embeddings"


class OpenAIEmbeddings:
    """OpenAI embeddings client using text-embedding-3-large (3072 dim)."""

    def __init__(self):
        settings = get_settings()
        self.api_key = settings.openai_api_key
        self.model = OPENAI_EMBEDDING_MODEL
        self.dimensions = OPENAI_EMBEDDING_DIM
        self.timeout = 30.0

    async def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        if not text or not text.strip():
            return [0.0] * self.dimensions

        embeddings = await self.embed_batch([text])
        return embeddings[0] if embeddings else [0.0] * self.dimensions

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        if not texts:
            return []

        # Filter empty texts but keep track of positions
        valid_texts = []
        valid_indices = []
        for i, text in enumerate(texts):
            if text and text.strip():
                valid_texts.append(text.strip())
                valid_indices.append(i)

        if not valid_texts:
            return [[0.0] * self.dimensions for _ in texts]

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    OPENAI_API_URL,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "input": valid_texts,
                        "dimensions": self.dimensions
                    }
                )
                response.raise_for_status()
                data = response.json()

                # Extract embeddings from response
                embeddings_data = data.get("data", [])
                embeddings_map = {item["index"]: item["embedding"] for item in embeddings_data}

                # Build result list maintaining original order
                result = [[0.0] * self.dimensions for _ in texts]
                for orig_idx, embed_idx in zip(valid_indices, range(len(valid_texts))):
                    if embed_idx in embeddings_map:
                        result[orig_idx] = embeddings_map[embed_idx]

                logger.debug(f"Generated {len(valid_texts)} embeddings")
                return result

        except Exception as e:
            logger.error(f"OpenAI embeddings failed: {e}")
            # Return zero vectors on failure
            return [[0.0] * self.dimensions for _ in texts]


# Singleton
openai_embeddings = OpenAIEmbeddings()
