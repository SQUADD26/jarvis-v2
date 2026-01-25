"""Document ingestion pipeline."""

import asyncio
import hashlib
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

from jarvis.rag.chunker import chunker, Chunk
from jarvis.integrations.crawl4ai_client import crawler
from jarvis.integrations.gemini import gemini
from jarvis.db.supabase import get_db
from jarvis.utils.logging import get_logger

logger = get_logger(__name__)


class IngestionPipeline:
    """Pipeline for ingesting documents into the RAG system."""

    def __init__(self):
        self.batch_size = 10  # Embeddings batch size

    async def ingest_url(
        self,
        url: str,
        user_id: str,
        doc_type: str = "webpage",
        custom_metadata: dict = None
    ) -> dict:
        """
        Ingest a URL into the RAG system.

        Args:
            url: The URL to crawl and ingest
            user_id: The user who owns this document
            doc_type: Type of document (webpage, article, documentation, etc.)
            custom_metadata: Optional additional metadata

        Returns:
            Dict with ingestion results
        """
        logger.info(f"Ingesting URL: {url}")

        # 1. Crawl the URL
        crawl_result = await crawler.scrape_url(url)

        if not crawl_result["success"]:
            return {
                "success": False,
                "error": f"Failed to crawl URL: {url}",
                "url": url
            }

        content = crawl_result["content"]
        title = crawl_result["title"] or self._extract_title_from_url(url)

        # 2. Build metadata
        metadata = {
            "source_type": doc_type,
            "source_url": url,
            "domain": urlparse(url).netloc,
            "title": title,
            "crawled_at": datetime.utcnow().isoformat(),
            "content_hash": hashlib.md5(content.encode()).hexdigest(),
            **(custom_metadata or {})
        }

        # 3. Chunk the content
        chunks = chunker.chunk_text(content, metadata)

        if not chunks:
            return {
                "success": False,
                "error": "No content to chunk",
                "url": url
            }

        # 4. Generate embeddings and store
        stored_chunks = await self._store_chunks(chunks, user_id, title, url)

        return {
            "success": True,
            "url": url,
            "title": title,
            "chunks_count": len(stored_chunks),
            "metadata": metadata
        }

    async def ingest_text(
        self,
        text: str,
        user_id: str,
        title: str,
        doc_type: str = "text",
        source_url: str = None,
        custom_metadata: dict = None
    ) -> dict:
        """
        Ingest raw text into the RAG system.

        Args:
            text: The text content to ingest
            user_id: The user who owns this document
            title: Document title
            doc_type: Type of document
            source_url: Optional source URL
            custom_metadata: Optional additional metadata

        Returns:
            Dict with ingestion results
        """
        logger.info(f"Ingesting text: {title[:50]}...")

        # Build metadata
        metadata = {
            "source_type": doc_type,
            "source_url": source_url,
            "title": title,
            "ingested_at": datetime.utcnow().isoformat(),
            "content_hash": hashlib.md5(text.encode()).hexdigest(),
            **(custom_metadata or {})
        }

        # Chunk the content
        chunks = chunker.chunk_text(text, metadata)

        if not chunks:
            return {
                "success": False,
                "error": "No content to chunk",
                "title": title
            }

        # Generate embeddings and store
        stored_chunks = await self._store_chunks(chunks, user_id, title, source_url)

        return {
            "success": True,
            "title": title,
            "chunks_count": len(stored_chunks),
            "metadata": metadata
        }

    async def ingest_multiple_urls(
        self,
        urls: list[str],
        user_id: str,
        doc_type: str = "webpage",
        concurrency: int = 3
    ) -> list[dict]:
        """
        Ingest multiple URLs concurrently.

        Args:
            urls: List of URLs to ingest
            user_id: The user who owns these documents
            doc_type: Type of documents
            concurrency: Max concurrent ingestions

        Returns:
            List of ingestion results
        """
        semaphore = asyncio.Semaphore(concurrency)

        async def ingest_with_semaphore(url: str) -> dict:
            async with semaphore:
                try:
                    return await self.ingest_url(url, user_id, doc_type)
                except Exception as e:
                    logger.error(f"Failed to ingest {url}: {e}")
                    return {"success": False, "url": url, "error": str(e)}

        tasks = [ingest_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks)

        success_count = sum(1 for r in results if r.get("success"))
        logger.info(f"Ingested {success_count}/{len(urls)} URLs successfully")

        return results

    async def _store_chunks(
        self,
        chunks: list[Chunk],
        user_id: str,
        title: str,
        source_url: str = None
    ) -> list[dict]:
        """Store chunks with embeddings in Supabase."""
        db = get_db()
        stored = []

        # Process in batches
        for i in range(0, len(chunks), self.batch_size):
            batch = chunks[i:i + self.batch_size]

            # Generate embeddings for batch
            texts = [c.content for c in batch]
            embeddings = await gemini.embed_batch(texts)

            # Store each chunk
            for chunk, embedding in zip(batch, embeddings):
                record = {
                    "user_id": user_id,
                    "title": title,
                    "content": chunk.content,
                    "embedding": embedding,
                    "chunk_index": chunk.index,
                    "metadata": chunk.metadata,
                    "source_url": source_url
                }

                try:
                    result = db.table("rag_documents").insert(record).execute()
                    if result.data:
                        stored.append(result.data[0])
                except Exception as e:
                    logger.error(f"Failed to store chunk {chunk.index}: {e}")

        logger.info(f"Stored {len(stored)} chunks for '{title}'")
        return stored

    def _extract_title_from_url(self, url: str) -> str:
        """Extract a reasonable title from URL."""
        parsed = urlparse(url)
        path = parsed.path.strip("/")
        if path:
            # Use last path segment
            title = path.split("/")[-1]
            # Clean up
            title = title.replace("-", " ").replace("_", " ")
            title = title.split(".")[0]  # Remove extension
            return title.title()
        return parsed.netloc


# Singleton
ingestion_pipeline = IngestionPipeline()
