"""Document ingestion pipeline with OpenAI embeddings and source tracking."""

import asyncio
import hashlib
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

from jarvis.rag.chunker import chunker, Chunk
from jarvis.integrations.crawl4ai_client import crawler
from jarvis.integrations.openai_embeddings import openai_embeddings
from jarvis.db.supabase_client import get_db
from jarvis.utils.logging import get_logger

logger = get_logger(__name__)


class IngestionPipeline:
    """Pipeline for ingesting documents into the RAG system with source tracking."""

    def __init__(self):
        self.batch_size = 20  # OpenAI can handle larger batches

    async def ingest_url(
        self,
        url: str,
        user_id: str,
        title: str = None,
        custom_metadata: dict = None
    ) -> dict:
        """
        Ingest a URL into the RAG system.

        Creates:
        1. One row in rag_sources (the parent)
        2. Multiple rows in rag_chunks (the children)
        """
        logger.info(f"Ingesting URL: {url}")

        # Check for duplicate by URL
        existing = await self._check_duplicate_url(url, user_id)
        if existing:
            return {
                "success": False,
                "error": f"URL già importato: {existing['title']}",
                "existing_source_id": existing["id"]
            }

        # 1. Crawl the URL
        crawl_result = await crawler.scrape_url(url)

        if not crawl_result.get("success"):
            return {
                "success": False,
                "error": f"Failed to crawl: {crawl_result.get('error', 'Unknown error')}",
                "url": url
            }

        content = crawl_result.get("content", "")
        crawled_title = crawl_result.get("title", "")
        final_title = title or crawled_title or self._extract_title_from_url(url)

        if not content or len(content) < 50:
            return {
                "success": False,
                "error": "Contenuto insufficiente dalla pagina",
                "url": url
            }

        # 2. Create source record
        content_hash = hashlib.md5(content.encode()).hexdigest()
        parsed_url = urlparse(url)

        source = await self._create_source(
            user_id=user_id,
            title=final_title,
            source_type="url",
            source_url=url,
            file_hash=content_hash,
            domain=parsed_url.netloc,
            content_length=len(content),
            metadata=custom_metadata or {}
        )

        if not source:
            return {"success": False, "error": "Failed to create source record"}

        # 3. Chunk the content
        chunk_metadata = {
            "source_url": url,
            "domain": parsed_url.netloc,
            "title": final_title
        }
        chunks = chunker.chunk_text(content, chunk_metadata)

        if not chunks:
            await self._delete_source(source["id"])
            return {"success": False, "error": "No content to chunk", "url": url}

        # 4. Store chunks with embeddings
        stored_count = await self._store_chunks(chunks, source["id"], user_id)

        # 5. Update source with final chunk count
        await self._update_source_status(source["id"], "active", stored_count)

        return {
            "success": True,
            "source_id": source["id"],
            "url": url,
            "title": final_title,
            "chunks_count": stored_count,
            "content_length": len(content)
        }

    async def ingest_text(
        self,
        text: str,
        user_id: str,
        title: str,
        source_type: str = "text",
        custom_metadata: dict = None
    ) -> dict:
        """
        Ingest raw text into the RAG system.
        """
        logger.info(f"Ingesting text: {title[:50]}...")

        if not text or len(text) < 20:
            return {"success": False, "error": "Testo troppo corto"}

        # Check for duplicate by hash
        content_hash = hashlib.md5(text.encode()).hexdigest()
        existing = await self._check_duplicate_hash(content_hash, user_id)
        if existing:
            return {
                "success": False,
                "error": f"Testo già importato: {existing['title']}",
                "existing_source_id": existing["id"]
            }

        # Create source record
        source = await self._create_source(
            user_id=user_id,
            title=title,
            source_type=source_type,
            file_hash=content_hash,
            content_length=len(text),
            metadata=custom_metadata or {}
        )

        if not source:
            return {"success": False, "error": "Failed to create source record"}

        # Chunk the content
        chunk_metadata = {"title": title, "source_type": source_type}
        chunks = chunker.chunk_text(text, chunk_metadata)

        if not chunks:
            await self._delete_source(source["id"])
            return {"success": False, "error": "No content to chunk"}

        # Store chunks with embeddings
        stored_count = await self._store_chunks(chunks, source["id"], user_id)

        # Update source status
        await self._update_source_status(source["id"], "active", stored_count)

        return {
            "success": True,
            "source_id": source["id"],
            "title": title,
            "chunks_count": stored_count
        }

    async def ingest_multiple_urls(
        self,
        urls: list[str],
        user_id: str,
        concurrency: int = 3
    ) -> list[dict]:
        """Ingest multiple URLs concurrently."""
        semaphore = asyncio.Semaphore(concurrency)

        async def ingest_with_semaphore(url: str) -> dict:
            async with semaphore:
                try:
                    return await self.ingest_url(url, user_id)
                except Exception as e:
                    logger.error(f"Failed to ingest {url}: {e}")
                    return {"success": False, "url": url, "error": str(e)}

        tasks = [ingest_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks)

        success_count = sum(1 for r in results if r.get("success"))
        logger.info(f"Ingested {success_count}/{len(urls)} URLs successfully")

        return results

    async def delete_source(self, source_id: str, user_id: str) -> bool:
        """Delete a source and all its chunks (CASCADE)."""
        db = get_db()
        try:
            result = db.table("rag_sources") \
                .delete() \
                .eq("id", source_id) \
                .eq("user_id", user_id) \
                .execute()
            return len(result.data) > 0 if result.data else False
        except Exception as e:
            logger.error(f"Failed to delete source {source_id}: {e}")
            return False

    async def list_sources(self, user_id: str, limit: int = 20) -> list[dict]:
        """List all sources for a user."""
        db = get_db()
        try:
            result = db.table("rag_sources") \
                .select("id, title, source_type, source_url, domain, chunks_count, status, created_at") \
                .eq("user_id", user_id) \
                .eq("status", "active") \
                .order("created_at", desc=True) \
                .limit(limit) \
                .execute()
            return result.data if result.data else []
        except Exception as e:
            logger.error(f"Failed to list sources: {e}")
            return []

    # === Private Methods ===

    async def _create_source(
        self,
        user_id: str,
        title: str,
        source_type: str,
        source_url: str = None,
        file_name: str = None,
        file_hash: str = None,
        domain: str = None,
        content_length: int = 0,
        metadata: dict = None
    ) -> Optional[dict]:
        """Create a source record."""
        db = get_db()
        try:
            result = db.table("rag_sources").insert({
                "user_id": user_id,
                "title": title,
                "source_type": source_type,
                "source_url": source_url,
                "file_name": file_name,
                "file_hash": file_hash,
                "domain": domain,
                "content_length": content_length,
                "metadata": metadata or {},
                "status": "processing"
            }).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Failed to create source: {e}")
            return None

    async def _update_source_status(
        self,
        source_id: str,
        status: str,
        chunks_count: int = None
    ) -> None:
        """Update source status and chunk count."""
        db = get_db()
        try:
            update_data = {"status": status, "updated_at": datetime.utcnow().isoformat()}
            if chunks_count is not None:
                update_data["chunks_count"] = chunks_count

            db.table("rag_sources") \
                .update(update_data) \
                .eq("id", source_id) \
                .execute()
        except Exception as e:
            logger.error(f"Failed to update source status: {e}")

    async def _delete_source(self, source_id: str) -> None:
        """Delete a source (used for cleanup on failure)."""
        db = get_db()
        try:
            db.table("rag_sources").delete().eq("id", source_id).execute()
        except Exception as e:
            logger.error(f"Failed to delete source: {e}")

    async def _check_duplicate_url(self, url: str, user_id: str) -> Optional[dict]:
        """Check if URL already exists for user."""
        db = get_db()
        try:
            result = db.table("rag_sources") \
                .select("id, title") \
                .eq("user_id", user_id) \
                .eq("source_url", url) \
                .eq("status", "active") \
                .limit(1) \
                .execute()
            return result.data[0] if result.data else None
        except Exception:
            return None

    async def _check_duplicate_hash(self, file_hash: str, user_id: str) -> Optional[dict]:
        """Check if content hash already exists for user."""
        db = get_db()
        try:
            result = db.table("rag_sources") \
                .select("id, title") \
                .eq("user_id", user_id) \
                .eq("file_hash", file_hash) \
                .eq("status", "active") \
                .limit(1) \
                .execute()
            return result.data[0] if result.data else None
        except Exception:
            return None

    async def _store_chunks(
        self,
        chunks: list[Chunk],
        source_id: str,
        user_id: str
    ) -> int:
        """Store chunks with OpenAI embeddings."""
        db = get_db()
        stored = 0

        # Process in batches
        for i in range(0, len(chunks), self.batch_size):
            batch = chunks[i:i + self.batch_size]

            # Generate embeddings with OpenAI
            texts = [c.content for c in batch]
            embeddings = await openai_embeddings.embed_batch(texts)

            # Store each chunk
            records = []
            for chunk, embedding in zip(batch, embeddings):
                records.append({
                    "source_id": source_id,
                    "user_id": user_id,
                    "content": chunk.content,
                    "chunk_index": chunk.index,
                    "embedding": embedding,
                    "start_char": chunk.start_char,
                    "end_char": chunk.end_char,
                    "metadata": chunk.metadata
                })

            try:
                result = db.table("rag_chunks").insert(records).execute()
                stored += len(result.data) if result.data else 0
            except Exception as e:
                logger.error(f"Failed to store chunk batch: {e}")

        logger.info(f"Stored {stored}/{len(chunks)} chunks")
        return stored

    def _extract_title_from_url(self, url: str) -> str:
        """Extract a reasonable title from URL."""
        parsed = urlparse(url)
        path = parsed.path.strip("/")
        if path:
            title = path.split("/")[-1]
            title = title.replace("-", " ").replace("_", " ")
            title = title.split(".")[0]
            return title.title() or parsed.netloc
        return parsed.netloc


# Singleton
ingestion_pipeline = IngestionPipeline()
