"""Task executor for background processing."""

import asyncio
from typing import Any
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from jarvis.config import get_settings
from jarvis.db.supabase_client import run_db
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
        task_id = task.get("id")
        if not task_id:
            logger.error(f"Task has no id, skipping: {task}")
            return {"success": False, "error": "Task has no id"}
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
            "notion_proactive_check": self._handle_notion_proactive_check,
            "daily_briefing": self._handle_daily_briefing,
            "email_monitor": self._handle_email_monitor,
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
            source_result = await run_db(lambda: db.table("rag_sources").insert({
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
            }).execute())

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
                    result = await run_db(lambda: db.table("rag_chunks").insert(records).execute())
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
                await run_db(lambda: db.table("rag_sources").delete().eq("id", source_id).execute())
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
            await run_db(lambda: db.table("rag_sources").update({
                "status": "active",
                "chunks_count": total_chunks
            }).eq("id", source_id).execute())
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

    async def _handle_notion_proactive_check(self, user_id: str, payload: dict) -> dict:
        """Handle proactive Notion task check - notify about due/overdue tasks."""
        from jarvis.integrations.notion import notion_client
        from jarvis.integrations.gemini import gemini
        from datetime import timedelta

        RESCHEDULE_HOURS = 3

        try:
            databases = await notion_client.discover_databases()
            if not databases:
                logger.info(f"Notion proactive check: no databases for user {user_id}")
                return {"type": "notion_proactive_check", "status": "no_databases"}

            now = datetime.utcnow()
            today = now.strftime("%Y-%m-%d")
            in_7_days = (now + timedelta(days=7)).strftime("%Y-%m-%d")

            actionable_tasks = {"overdue": [], "today": [], "this_week": []}

            async def _check_database(db):
                """Check a single database for actionable tasks."""
                results = []
                try:
                    schema = await notion_client.get_database_schema(db["id"])
                    props = schema.get("properties", {})

                    # Find date property
                    date_prop_name = None
                    for name, info in props.items():
                        if info["type"] == "date":
                            date_prop_name = name
                            break

                    if not date_prop_name:
                        return results

                    # Build filter: date <= 7 days from now, not completed
                    filter_obj = {
                        "and": [
                            {"property": date_prop_name, "date": {"on_or_before": in_7_days}},
                            {"property": date_prop_name, "date": {"is_not_empty": True}},
                        ]
                    }

                    # Add status filter if available (exclude completed)
                    for name, info in props.items():
                        if info["type"] == "status":
                            done_options = [
                                o for o in info.get("options", [])
                                if o.lower() in ("done", "completato", "completata", "fatto", "fatta", "completed", "chiuso", "chiusa")
                            ]
                            for done_opt in done_options:
                                filter_obj["and"].append({
                                    "property": name,
                                    "status": {"does_not_equal": done_opt},
                                })
                            break

                    tasks = await notion_client.query_database(db["id"], filter_obj)

                    # Find title property name
                    title_prop_name = None
                    for name, info in props.items():
                        if info["type"] == "title":
                            title_prop_name = name
                            break

                    for task in tasks:
                        date_val = task.get(date_prop_name)
                        if not date_val:
                            continue
                        due_str = date_val.get("start") if isinstance(date_val, dict) else str(date_val)
                        if not due_str:
                            continue
                        task_title = task.get(title_prop_name, "Senza titolo") if title_prop_name else "Senza titolo"
                        results.append({
                            "title": task_title,
                            "due": due_str,
                            "database": db["title"],
                        })
                except Exception as e:
                    logger.warning(f"Failed to query {db['title']} for proactive check: {e}")
                return results

            # Query all databases in parallel
            db_results = await asyncio.gather(*[_check_database(db) for db in databases])

            for task_list in db_results:
                for task_info in task_list:
                    due_str = task_info["due"]
                    if due_str < today:
                        actionable_tasks["overdue"].append(task_info)
                    elif due_str == today:
                        actionable_tasks["today"].append(task_info)
                    else:
                        actionable_tasks["this_week"].append(task_info)

            # Only notify if there are actionable tasks
            total = sum(len(v) for v in actionable_tasks.values())
            if total > 0:
                # Generate digest with LLM
                gemini.set_user_context(user_id)
                digest_prompt = f"""Genera un breve digest delle task in scadenza per l'utente. Sii conciso e utile.

TASK SCADUTE ({len(actionable_tasks['overdue'])}):
{chr(10).join(f"- {t['title']} (scadenza: {t['due']}, db: {t['database']})" for t in actionable_tasks['overdue']) or "Nessuna"}

TASK DI OGGI ({len(actionable_tasks['today'])}):
{chr(10).join(f"- {t['title']} (db: {t['database']})" for t in actionable_tasks['today']) or "Nessuna"}

TASK QUESTA SETTIMANA ({len(actionable_tasks['this_week'])}):
{chr(10).join(f"- {t['title']} (scadenza: {t['due']}, db: {t['database']})" for t in actionable_tasks['this_week']) or "Nessuna"}

Scrivi un messaggio breve in italiano, usa emoji per rendere il tutto leggibile. Non usare markdown."""

                digest = await gemini.generate(
                    digest_prompt,
                    model="gemini-2.5-flash",
                    temperature=0.3,
                )

                await notifier.notify_task_completed(user_id, "📋 Task Notion", digest)

            result = {
                "type": "notion_proactive_check",
                "overdue": len(actionable_tasks["overdue"]),
                "today": len(actionable_tasks["today"]),
                "this_week": len(actionable_tasks["this_week"]),
                "notified": total > 0,
            }

        except Exception as e:
            logger.error(f"Notion proactive check failed: {e}")
            result = {"type": "notion_proactive_check", "error": str(e)}

        # Always reschedule next check (even on error)
        try:
            next_check = datetime.utcnow() + timedelta(hours=RESCHEDULE_HOURS)
            await TaskRepository.enqueue(
                user_id=user_id,
                task_type="notion_proactive_check",
                payload={},
                scheduled_at=next_check,
                priority=8,
            )
            logger.info(f"Notion proactive check rescheduled for {next_check.isoformat()}")
        except Exception as e:
            logger.error(f"Failed to reschedule notion proactive check: {e}")

        return result

    async def _handle_daily_briefing(self, user_id: str, payload: dict) -> dict:
        """Handle daily briefing - morning or evening digest."""
        from jarvis.integrations.google_calendar import GoogleCalendarClient
        from jarvis.integrations.gmail import GmailClient
        from jarvis.integrations.notion import notion_client
        from jarvis.integrations.gemini import gemini

        briefing_type = payload.get("briefing_type", "morning")  # "morning" or "evening"
        
        try:
            # Setup timezone
            tz = ZoneInfo(settings.briefing_timezone)
            now_local = datetime.now(tz)
            today_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
            today_end = today_start + timedelta(days=1)
            tomorrow_start = today_end
            tomorrow_end = tomorrow_start + timedelta(days=1)

            briefing_parts = []

            # === CALENDAR EVENTS ===
            try:
                calendar_client = GoogleCalendarClient()
                if briefing_type == "morning":
                    # Morning: today's events
                    events = calendar_client.get_events(
                        start=today_start,
                        end=today_end,
                        max_results=20
                    )
                    if events:
                        briefing_parts.append(f"EVENTI DI OGGI ({len(events)}):")
                        for evt in events:
                            evt_time = evt.get("start", {}).get("dateTime") or evt.get("start", {}).get("date", "")
                            briefing_parts.append(f"- {evt.get('summary', 'Senza titolo')} ({evt_time})")
                    else:
                        briefing_parts.append("EVENTI DI OGGI: Nessun evento in agenda.")
                else:
                    # Evening: tomorrow's events preview
                    events = calendar_client.get_events(
                        start=tomorrow_start,
                        end=tomorrow_end,
                        max_results=20
                    )
                    if events:
                        briefing_parts.append(f"EVENTI DI DOMANI ({len(events)}):")
                        for evt in events:
                            evt_time = evt.get("start", {}).get("dateTime") or evt.get("start", {}).get("date", "")
                            briefing_parts.append(f"- {evt.get('summary', 'Senza titolo')} ({evt_time})")
                    else:
                        briefing_parts.append("EVENTI DI DOMANI: Nessun evento in agenda.")
            except Exception as e:
                logger.warning(f"Failed to fetch calendar events for briefing: {e}")
                briefing_parts.append("CALENDARIO: Non disponibile.")

            # === EMAIL ===
            try:
                gmail_client = GmailClient()
                if briefing_type == "morning":
                    # Morning: unread emails
                    emails = gmail_client.get_inbox(max_results=10, unread_only=True)
                    if emails:
                        briefing_parts.append(f"\nEMAIL NON LETTE ({len(emails)}):")
                        for email in emails:
                            briefing_parts.append(f"- Da: {email.get('from', 'Sconosciuto')}, Oggetto: {email.get('subject', 'Nessun oggetto')}")
                    else:
                        briefing_parts.append("\nEMAIL NON LETTE: Nessuna.")
                else:
                    # Evening: today's emails
                    today_str = today_start.strftime("%Y/%m/%d")
                    emails = gmail_client.get_inbox(max_results=10, query=f"after:{today_str}")
                    if emails:
                        briefing_parts.append(f"\nEMAIL DI OGGI ({len(emails)}):")
                        for email in emails:
                            briefing_parts.append(f"- Da: {email.get('from', 'Sconosciuto')}, Oggetto: {email.get('subject', 'Nessun oggetto')}")
                    else:
                        briefing_parts.append("\nEMAIL DI OGGI: Nessuna.")
            except Exception as e:
                logger.warning(f"Failed to fetch emails for briefing: {e}")
                briefing_parts.append("\nEMAIL: Non disponibili.")

            # === NOTION TASKS ===
            try:
                databases = await notion_client.discover_databases()
                if databases:
                    today_str = today_start.strftime("%Y-%m-%d")
                    tasks_today = []
                    tasks_overdue = []

                    for db in databases:
                        try:
                            schema = await notion_client.get_database_schema(db["id"])
                            props = schema.get("properties", {})

                            # Find date and title properties
                            date_prop_name = None
                            title_prop_name = None
                            for name, info in props.items():
                                if info["type"] == "date":
                                    date_prop_name = name
                                if info["type"] == "title":
                                    title_prop_name = name

                            if not date_prop_name:
                                continue

                            # Query tasks due today or overdue
                            filter_obj = {
                                "and": [
                                    {"property": date_prop_name, "date": {"on_or_before": today_str}},
                                    {"property": date_prop_name, "date": {"is_not_empty": True}},
                                ]
                            }

                            # Exclude completed tasks
                            for name, info in props.items():
                                if info["type"] == "status":
                                    done_options = [
                                        o for o in info.get("options", [])
                                        if o.lower() in ("done", "completato", "completata", "fatto", "fatta", "completed", "chiuso", "chiusa")
                                    ]
                                    for done_opt in done_options:
                                        filter_obj["and"].append({
                                            "property": name,
                                            "status": {"does_not_equal": done_opt},
                                        })
                                    break

                            tasks = await notion_client.query_database(db["id"], filter_obj)

                            for task in tasks:
                                date_val = task.get(date_prop_name)
                                if not date_val:
                                    continue
                                due_str = date_val.get("start") if isinstance(date_val, dict) else str(date_val)
                                if not due_str:
                                    continue
                                task_title = task.get(title_prop_name, "Senza titolo") if title_prop_name else "Senza titolo"
                                
                                if due_str == today_str:
                                    tasks_today.append(f"- {task_title} (da: {db['title']})")
                                elif due_str < today_str:
                                    tasks_overdue.append(f"- {task_title} (scadenza: {due_str}, da: {db['title']})")

                        except Exception as e:
                            logger.warning(f"Failed to query Notion database {db['title']} for briefing: {e}")

                    if tasks_overdue:
                        briefing_parts.append(f"\nTASK NOTION SCADUTE ({len(tasks_overdue)}):")
                        briefing_parts.extend(tasks_overdue)
                    
                    if tasks_today:
                        briefing_parts.append(f"\nTASK NOTION DI OGGI ({len(tasks_today)}):")
                        briefing_parts.extend(tasks_today)
                    
                    if not tasks_overdue and not tasks_today:
                        briefing_parts.append("\nTASK NOTION: Nessuna task in scadenza oggi.")
                else:
                    briefing_parts.append("\nTASK NOTION: Nessun database configurato.")
            except Exception as e:
                logger.warning(f"Failed to fetch Notion tasks for briefing: {e}")
                briefing_parts.append("\nTASK NOTION: Non disponibili.")

            # === GENERATE LLM DIGEST ===
            raw_data = "\n".join(briefing_parts)
            gemini.set_user_context(user_id)
            
            digest_prompt = f"""Genera un briefing {briefing_type} per l'utente. Sii conciso, utile e usa emoji per rendere il tutto più leggibile.

DATI:
{raw_data}

Scrivi un messaggio breve in italiano, ben formattato. Non usare markdown. Usa emoji appropriate per sezioni (📅 calendario, 📧 email, 📋 task)."""

            digest = await gemini.generate(
                digest_prompt,
                model="gemini-2.5-flash",
                temperature=0.4,
            )

            # === NOTIFY USER ===
            title = f"☀️ Briefing mattutino" if briefing_type == "morning" else f"🌙 Briefing serale"
            await notifier.notify_task_completed(user_id, title, digest)

            # === SCHEDULE NEXT BRIEFING ===
            await self._schedule_next_briefing(user_id, briefing_type)

            return {
                "type": "daily_briefing",
                "briefing_type": briefing_type,
                "status": "completed",
            }

        except Exception as e:
            logger.error(f"Daily briefing failed: {e}")
            # Still try to schedule next briefing even on error
            try:
                await self._schedule_next_briefing(user_id, briefing_type)
            except Exception as schedule_error:
                logger.error(f"Failed to reschedule briefing after error: {schedule_error}")
            
            return {
                "type": "daily_briefing",
                "briefing_type": briefing_type,
                "error": str(e),
            }

    async def _schedule_next_briefing(self, user_id: str, current_briefing_type: str):
        """Schedule the next briefing (morning -> evening -> morning)."""
        tz = ZoneInfo(settings.briefing_timezone)
        now_local = datetime.now(tz)

        if current_briefing_type == "morning":
            # After morning -> schedule evening for today
            next_type = "evening"
            next_local = now_local.replace(
                hour=settings.briefing_evening_hour,
                minute=settings.briefing_evening_minute,
                second=0,
                microsecond=0
            )
            # If evening time already passed today, schedule for tomorrow
            if next_local <= now_local:
                next_local += timedelta(days=1)
        else:
            # After evening -> schedule morning for tomorrow
            next_type = "morning"
            next_local = now_local.replace(
                hour=settings.briefing_morning_hour,
                minute=settings.briefing_morning_minute,
                second=0,
                microsecond=0
            ) + timedelta(days=1)

        # Convert to UTC for storage
        next_utc = next_local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)

        await TaskRepository.enqueue(
            user_id=user_id,
            task_type="daily_briefing",
            payload={"briefing_type": next_type},
            scheduled_at=next_utc,
            priority=9,
        )

        logger.info(f"Next {next_type} briefing scheduled for {next_local.isoformat()} (UTC: {next_utc.isoformat()})")

    async def _handle_email_monitor(self, user_id: str, payload: dict) -> dict:
        """Handle periodic email monitoring with smart filtering."""
        from jarvis.integrations.gmail import GmailClient
        from jarvis.integrations.gemini import gemini
        from jarvis.core.knowledge_graph import knowledge_graph
        from jarvis.db.redis_client import redis_client
        import re

        RESCHEDULE_MINUTES = 15
        URGENCY_KEYWORDS = [
            "urgente", "urgent", "asap", "scadenza", "deadline",
            "importante", "critical", "critico", "immediato", "subito",
        ]

        logger.info(f"Email monitor check for user {user_id}")

        redis_key = f"email_monitor:last_check:{user_id}"
        last_check = await redis_client.get(redis_key)
        last_check_ts = last_check if last_check else None

        try:
            gmail = GmailClient()

            query = "is:unread"
            if last_check_ts:
                query += f" after:{int(last_check_ts)}"

            emails = gmail.get_inbox(
                max_results=20,
                query=query,
                fetch_full_details=False
            )

            if not emails:
                await redis_client.set(
                    redis_key,
                    int(datetime.utcnow().timestamp()),
                    ttl=86400 * 7
                )
                await self._reschedule_email_monitor(user_id, RESCHEDULE_MINUTES)
                return {"type": "email_monitor", "new_emails": 0, "notified": False}

            important_emails = []

            for email in emails:
                sender = email.get("from", "")
                subject = email.get("subject", "")
                snippet = email.get("snippet", "")
                is_important = False
                reason = ""

                sender_name = re.sub(r"<.*?>", "", sender).strip()

                try:
                    entities = await knowledge_graph.search_entities(
                        sender_name[:50], limit=1, threshold=0.8
                    )
                    if entities:
                        is_important = True
                        reason = f"Contatto noto: {entities[0].get('name', sender_name)}"
                except Exception:
                    pass

                if not is_important:
                    text_to_check = f"{subject} {snippet}".lower()
                    for kw in URGENCY_KEYWORDS:
                        if kw in text_to_check:
                            is_important = True
                            reason = f"Keyword: {kw}"
                            break

                if is_important:
                    important_emails.append({
                        "from": sender,
                        "subject": subject,
                        "snippet": snippet[:150],
                        "reason": reason,
                    })

            await redis_client.set(
                redis_key,
                int(datetime.utcnow().timestamp()),
                ttl=86400 * 7
            )

            notified = False
            if important_emails:
                gemini.set_user_context(user_id)

                email_list = "\n".join([
                    f"- Da: {e['from']} — Oggetto: {e['subject']} (motivo: {e['reason']})"
                    for e in important_emails
                ])

                digest_prompt = f"""Hai ricevuto {len(important_emails)} email importanti.
Genera una notifica breve e chiara in italiano. Usa <b> per enfasi. Non usare markdown.
Indica chi scrive, l'oggetto e perche e importante.

EMAIL:
{email_list}

Notifica:"""

                digest = await gemini.generate(
                    digest_prompt,
                    model="gemini-2.5-flash",
                    temperature=0.3,
                )

                await notifier.notify_task_completed(
                    user_id,
                    f"📧 {len(important_emails)} email importanti",
                    digest
                )
                notified = True

        except Exception as e:
            logger.error(f"Email monitor failed: {e}")
            await self._reschedule_email_monitor(user_id, RESCHEDULE_MINUTES)
            return {"type": "email_monitor", "error": str(e)}

        await self._reschedule_email_monitor(user_id, RESCHEDULE_MINUTES)

        return {
            "type": "email_monitor",
            "total_new": len(emails),
            "important": len(important_emails),
            "notified": notified,
        }

    async def _reschedule_email_monitor(self, user_id: str, minutes: int):
        """Reschedule email monitor."""
        try:
            next_check = datetime.utcnow() + timedelta(minutes=minutes)
            await TaskRepository.enqueue(
                user_id=user_id,
                task_type="email_monitor",
                payload={},
                scheduled_at=next_check,
                priority=7,
            )
            logger.info(f"Email monitor rescheduled for {next_check.isoformat()}")
        except Exception as e:
            logger.error(f"Failed to reschedule email monitor: {e}")

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
