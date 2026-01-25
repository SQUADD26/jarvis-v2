"""Task executor for background processing."""

import asyncio
from typing import Any
from datetime import datetime

from jarvis.config import get_settings
from jarvis.db.repositories import TaskRepository
from jarvis.worker.notifier import notifier
from jarvis.core.orchestrator import process_message
from jarvis.rag.ingestion import ingestion_pipeline
from jarvis.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class TaskExecutor:
    """Executes background tasks based on their type."""

    async def execute(self, task: dict) -> dict:
        """Execute a task and return the result."""
        task_id = task["id"]
        task_type = task["task_type"]
        user_id = task["user_id"]
        payload = task.get("payload", {})

        logger.info(f"Executing task {task_id} type={task_type} for user={user_id}")

        # Mark as running
        await TaskRepository.start_task(task_id)

        try:
            # Dispatch to appropriate handler
            handler = self._get_handler(task_type)
            result = await handler(user_id, payload)

            # Mark as completed
            await TaskRepository.complete_task(task_id, result)

            logger.info(f"Task {task_id} completed successfully")
            return {"success": True, "result": result}

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Task {task_id} failed: {error_msg}")

            # Mark as failed (may retry automatically)
            await TaskRepository.fail_task(task_id, error_msg)

            return {"success": False, "error": error_msg}

    def _get_handler(self, task_type: str):
        """Get the handler function for a task type."""
        handlers = {
            "reminder": self._handle_reminder,
            "scheduled_check": self._handle_scheduled_check,
            "long_running": self._handle_long_running,
            "rag_ingest": self._handle_rag_ingest,
            "rag_deep_crawl": self._handle_rag_deep_crawl,
        }
        return handlers.get(task_type, self._handle_unknown)

    async def _handle_reminder(self, user_id: str, payload: dict) -> dict:
        """Handle reminder tasks."""
        message = payload.get("message", "Promemoria senza messaggio")

        await notifier.notify_reminder(user_id, message)

        return {
            "type": "reminder",
            "message": message,
            "delivered_at": datetime.utcnow().isoformat()
        }

    async def _handle_scheduled_check(self, user_id: str, payload: dict) -> dict:
        """Handle scheduled check tasks (calendar, email, etc.)."""
        check_type = payload.get("check_type", "general")
        query = payload.get("query", "")

        # Use the orchestrator to process the query
        if query:
            response = await process_message(user_id, query)
            await notifier.notify_task_completed(user_id, f"Controllo {check_type}", response)
            return {
                "type": "scheduled_check",
                "check_type": check_type,
                "response": response
            }

        return {
            "type": "scheduled_check",
            "check_type": check_type,
            "status": "no_query"
        }

    async def _handle_long_running(self, user_id: str, payload: dict) -> dict:
        """Handle long-running tasks."""
        query = payload.get("query", "")
        notify_start = payload.get("notify_start", True)
        notify_complete = payload.get("notify_complete", True)

        if notify_start:
            description = payload.get("description", query[:50] + "..." if len(query) > 50 else query)
            await notifier.notify_task_started(user_id, "Elaborazione", description)

        # Process the query
        response = await process_message(user_id, query)

        if notify_complete:
            await notifier.notify_task_completed(user_id, "Elaborazione", response)

        return {
            "type": "long_running",
            "query": query,
            "response": response
        }

    async def _handle_rag_ingest(self, user_id: str, payload: dict) -> dict:
        """Handle RAG URL ingestion tasks."""
        url = payload.get("url", "")
        title = payload.get("title")
        notify = payload.get("notify", True)

        if not url:
            return {"type": "rag_ingest", "success": False, "error": "URL mancante"}

        # Ingest the URL
        result = await ingestion_pipeline.ingest_url(
            url=url,
            user_id=user_id,
            title=title
        )

        if notify:
            if result.get("success"):
                await notifier.notify_task_completed(
                    user_id,
                    "📚 Importazione completata",
                    f"Ho importato '{result.get('title', url)}' con {result.get('chunks_count', 0)} chunk."
                )
            else:
                await notifier.notify_task_completed(
                    user_id,
                    "❌ Importazione fallita",
                    f"Errore: {result.get('error', 'Errore sconosciuto')}"
                )

        return {
            "type": "rag_ingest",
            **result
        }

    async def _handle_rag_deep_crawl(self, user_id: str, payload: dict) -> dict:
        """Handle RAG deep crawl tasks - creates ONE source with all chunks."""
        from jarvis.integrations.crawl4ai_client import crawler
        from jarvis.rag.chunker import chunker
        from jarvis.integrations.openai_embeddings import openai_embeddings
        from jarvis.db.supabase_client import get_db
        from urllib.parse import urlparse
        import hashlib

        url = payload.get("url", "")
        title = payload.get("title", "")
        max_depth = payload.get("max_depth", 2)
        max_pages = payload.get("max_pages", 50)
        notify = payload.get("notify", True)

        if not url:
            return {"type": "rag_deep_crawl", "success": False, "error": "URL mancante"}

        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        collection_title = title or f"Docs: {domain}"

        if notify:
            await notifier.notify_task_started(
                user_id,
                "🕷️ Deep crawl avviato",
                f"Sto crawlando {url} (max {max_pages} pagine)..."
            )

        # Deep crawl
        crawl_result = await crawler.deep_crawl(
            url=url,
            max_depth=max_depth,
            max_pages=max_pages
        )

        if not crawl_result.get("success"):
            if notify:
                await notifier.notify_task_completed(
                    user_id,
                    "❌ Crawl fallito",
                    "Nessuna pagina trovata"
                )
            return {"type": "rag_deep_crawl", "success": False, "error": "Crawl fallito"}

        pages = crawl_result.get("pages", [])
        valid_pages = [p for p in pages if p.get("content") and len(p["content"]) > 100]

        if not valid_pages:
            if notify:
                await notifier.notify_task_completed(
                    user_id,
                    "❌ Crawl fallito",
                    "Nessuna pagina con contenuto valido"
                )
            return {"type": "rag_deep_crawl", "success": False, "error": "Nessun contenuto valido"}

        # Calculate total content for hash
        all_content = "\n".join([p["content"] for p in valid_pages])
        content_hash = hashlib.md5(all_content.encode()).hexdigest()

        db = get_db()

        # Create ONE source for the entire documentation
        try:
            source_result = db.table("rag_sources").insert({
                "user_id": user_id,
                "title": collection_title,
                "source_type": "url",
                "source_url": url,
                "file_hash": content_hash,
                "domain": domain,
                "content_length": len(all_content),
                "metadata": {
                    "pages_count": len(valid_pages),
                    "max_depth": max_depth
                },
                "status": "processing"
            }).execute()

            if not source_result.data:
                raise Exception("Failed to create source")

            source_id = source_result.data[0]["id"]
        except Exception as e:
            logger.error(f"Failed to create source: {e}")
            if notify:
                await notifier.notify_task_completed(
                    user_id,
                    "❌ Errore",
                    f"Impossibile creare source: {e}"
                )
            return {"type": "rag_deep_crawl", "success": False, "error": str(e)}

        # Chunk all pages and store with the SAME source_id
        total_chunks = 0
        chunk_index = 0
        ingestion_failed = False

        try:
            for page in valid_pages:
            page_url = page.get("url", "")
            page_title = page.get("title", "")

            # Chunk this page's content
            chunk_metadata = {
                "page_url": page_url,
                "page_title": page_title,
                "crawl_depth": page.get("depth", 0)
            }
            page_chunks = chunker.chunk_text(page["content"], chunk_metadata)

            if not page_chunks:
                continue

            # Generate embeddings
            texts = [c.content for c in page_chunks]
            embeddings = await openai_embeddings.embed_batch(texts)

            # Prepare records - all linked to the SAME source
            records = []
            for chunk, embedding in zip(page_chunks, embeddings):
                records.append({
                    "source_id": source_id,
                    "user_id": user_id,
                    "content": chunk.content,
                    "chunk_index": chunk_index,
                    "embedding": embedding,
                    "start_char": chunk.start_char,
                    "end_char": chunk.end_char,
                    "metadata": {
                        **chunk.metadata,
                        "page_url": page_url,
                        "page_title": page_title
                    }
                })
                chunk_index += 1

            # Batch insert chunks
            try:
                result = db.table("rag_chunks").insert(records).execute()
                total_chunks += len(result.data) if result.data else 0
            except Exception as e:
                logger.error(f"Failed to store chunks for {page_url}: {e}")
                ingestion_failed = True
                break

        except Exception as e:
            logger.error(f"Deep crawl ingestion failed: {e}")
            ingestion_failed = True

        # Cleanup on failure - delete source (CASCADE deletes chunks)
        if ingestion_failed or total_chunks == 0:
            try:
                db.table("rag_sources").delete().eq("id", source_id).execute()
                logger.info(f"Cleaned up failed source {source_id}")
            except Exception as cleanup_error:
                logger.error(f"Failed to cleanup source: {cleanup_error}")

            if notify:
                await notifier.notify_task_completed(
                    user_id,
                    "❌ Importazione fallita",
                    "Errore durante l'elaborazione dei contenuti"
                )
            return {"type": "rag_deep_crawl", "success": False, "error": "Ingestion failed"}

        # Update source with final status and chunk count
        try:
            db.table("rag_sources").update({
                "status": "active",
                "chunks_count": total_chunks
            }).eq("id", source_id).execute()
        except Exception as e:
            logger.error(f"Failed to update source status: {e}")

        if notify:
            await notifier.notify_task_completed(
                user_id,
                "✅ Deep crawl completato",
                f"Importato '{collection_title}': {len(valid_pages)} pagine, {total_chunks} chunks."
            )

        return {
            "type": "rag_deep_crawl",
            "success": True,
            "source_id": source_id,
            "pages_crawled": len(valid_pages),
            "total_chunks": total_chunks
        }

    async def _handle_unknown(self, user_id: str, payload: dict) -> dict:
        """Handle unknown task types."""
        logger.warning(f"Unknown task type for user {user_id}: {payload}")
        return {
            "type": "unknown",
            "status": "skipped",
            "reason": "Unknown task type"
        }


# Singleton instance
executor = TaskExecutor()
