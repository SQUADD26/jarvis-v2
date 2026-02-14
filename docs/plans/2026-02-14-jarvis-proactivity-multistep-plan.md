# Jarvis v2 — Proattivita e Multi-step Reasoning Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add morning/evening briefing, email monitoring with smart filtering, and multi-step reasoning with self-correction to Jarvis v2.

**Architecture:** Three features built incrementally. Features 1-2 follow the existing `notion_proactive_check` pattern (auto-rescheduling task types in the worker). Feature 3 modifies the LangGraph orchestrator to support sequential step execution with a verification loop. All features are backward-compatible.

**Tech Stack:** Python 3.12, LangGraph, Gemini 2.5 Flash, Supabase (task queue), Redis (state tracking), Telegram (notifications)

---

## Feature 1: Daily Briefing (Morning + Evening)

### Task 1.1: Add briefing config to Settings

**Files:**
- Modify: `src/jarvis/config.py` (Settings class, around line 80)

**Step 1: Add briefing settings**

Add these fields to the `Settings` class, before `model_config`:

```python
    # Briefing
    briefing_morning_hour: int = 7
    briefing_morning_minute: int = 30
    briefing_evening_hour: int = 20
    briefing_evening_minute: int = 0
    briefing_user_id: str = Field(default="", alias="BRIEFING_USER_ID")  # Telegram chat_id
    briefing_timezone: str = Field(default="Europe/Rome", alias="BRIEFING_TIMEZONE")
```

**Step 2: Verify**

Run: `cd /home/ubuntu/ai-agents && python -c "from jarvis.config import get_settings; s = get_settings(); print(s.briefing_morning_hour, s.briefing_timezone)"`
Expected: `7 Europe/Rome`

**Step 3: Commit**

```bash
git add src/jarvis/config.py
git commit -m "feat: add briefing schedule config to Settings"
```

---

### Task 1.2: Implement daily briefing handler in executor

**Files:**
- Modify: `src/jarvis/worker/executor.py`

**Context:** The handler follows the same pattern as `_handle_notion_proactive_check` (lines 310-508). It:
1. Calls Calendar, Gmail, and Notion APIs directly (not through the orchestrator)
2. Generates a unified digest with LLM
3. Sends via TelegramNotifier
4. Auto-reschedules to next briefing slot

**Step 1: Add imports at top of executor.py**

After the existing imports (around line 8), add:

```python
from zoneinfo import ZoneInfo
```

**Step 2: Register handler in `_get_handler`**

In the `_get_handler` method (line 57), add to the `handlers` dict:

```python
            "daily_briefing": self._handle_daily_briefing,
            "email_monitor": self._handle_email_monitor,
```

**Step 3: Implement `_handle_daily_briefing` method**

Add this method to `TaskExecutor` class, after `_handle_notion_proactive_check`:

```python
    async def _handle_daily_briefing(self, user_id: str, payload: dict) -> dict:
        """Handle daily briefing - morning or evening digest."""
        from jarvis.integrations.google_calendar import GoogleCalendarClient
        from jarvis.integrations.gmail import GmailClient
        from jarvis.integrations.notion import notion_client
        from jarvis.integrations.gemini import gemini
        from datetime import timedelta

        briefing_type = payload.get("briefing_type", "morning")  # "morning" or "evening"
        tz = ZoneInfo(settings.briefing_timezone)
        now_local = datetime.utcnow().replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)
        today_str = now_local.strftime("%A %d %B %Y")

        logger.info(f"Daily briefing ({briefing_type}) for user {user_id}")

        sections = []

        # 1. Calendar events
        try:
            cal = GoogleCalendarClient()
            if briefing_type == "morning":
                # Today's events
                start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
                end = start + timedelta(days=1)
            else:
                # Tomorrow's events (preview)
                start = (now_local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                end = start + timedelta(days=1)

            events = cal.get_events(
                start=start.astimezone(ZoneInfo("UTC")).replace(tzinfo=None),
                end=end.astimezone(ZoneInfo("UTC")).replace(tzinfo=None),
                max_results=20
            )

            if events:
                label = "AGENDA DI OGGI" if briefing_type == "morning" else "AGENDA DI DOMANI"
                event_lines = []
                for e in events:
                    start_time = e.get("start", {}).get("dateTime", e.get("start", {}).get("date", ""))
                    title = e.get("summary", "Senza titolo")
                    event_lines.append(f"- {start_time}: {title}")
                sections.append(f"{label}:\n" + "\n".join(event_lines))
            else:
                label = "oggi" if briefing_type == "morning" else "domani"
                sections.append(f"CALENDARIO: Nessun evento {label}.")
        except Exception as e:
            logger.warning(f"Briefing calendar failed: {e}")
            sections.append(f"CALENDARIO: Errore nel recupero ({e})")

        # 2. Unread emails
        try:
            gmail = GmailClient()
            if briefing_type == "morning":
                emails = gmail.get_inbox(max_results=10, unread_only=True)
            else:
                # Evening: emails received today
                today_query = f"after:{now_local.strftime('%Y/%m/%d')}"
                emails = gmail.get_inbox(max_results=10, query=today_query)

            if emails:
                email_lines = []
                for e in emails[:10]:
                    sender = e.get("from", "Sconosciuto")
                    subject = e.get("subject", "Nessun oggetto")
                    email_lines.append(f"- Da: {sender} — {subject}")
                label = "EMAIL NON LETTE" if briefing_type == "morning" else "EMAIL DI OGGI"
                sections.append(f"{label} ({len(emails)}):\n" + "\n".join(email_lines))
            else:
                sections.append("EMAIL: Nessuna email rilevante.")
        except Exception as e:
            logger.warning(f"Briefing email failed: {e}")
            sections.append(f"EMAIL: Errore nel recupero ({e})")

        # 3. Notion tasks (due today/overdue)
        try:
            databases = await notion_client.discover_databases()
            task_lines = []
            if databases:
                for db in databases[:5]:
                    try:
                        schema = await notion_client.get_database_schema(db["id"])
                        props = schema.get("properties", {})

                        date_prop = None
                        title_prop = None
                        for name, info in props.items():
                            if info["type"] == "date" and not date_prop:
                                date_prop = name
                            if info["type"] == "title" and not title_prop:
                                title_prop = name

                        if not date_prop:
                            continue

                        today_iso = now_local.strftime("%Y-%m-%d")
                        filter_obj = {
                            "and": [
                                {"property": date_prop, "date": {"on_or_before": today_iso}},
                                {"property": date_prop, "date": {"is_not_empty": True}},
                            ]
                        }
                        tasks = await notion_client.query_database(db["id"], filter_obj)
                        for t in tasks[:5]:
                            t_title = t.get(title_prop, "Senza titolo") if title_prop else "Senza titolo"
                            t_due = t.get(date_prop, {})
                            due_str = t_due.get("start", "") if isinstance(t_due, dict) else str(t_due)
                            overdue = " (SCADUTA)" if due_str < today_iso else ""
                            task_lines.append(f"- {t_title} — scadenza: {due_str}{overdue} [{db['title']}]")
                    except Exception as e:
                        logger.warning(f"Briefing notion db {db.get('title')} failed: {e}")

            if task_lines:
                sections.append(f"TASK IN SCADENZA ({len(task_lines)}):\n" + "\n".join(task_lines))
            else:
                sections.append("TASK: Nessuna task in scadenza.")
        except Exception as e:
            logger.warning(f"Briefing notion failed: {e}")
            sections.append(f"TASK: Errore nel recupero ({e})")

        # 4. Generate digest with LLM
        raw_data = "\n\n".join(sections)
        gemini.set_user_context(user_id)

        if briefing_type == "morning":
            digest_prompt = f"""Genera un briefing mattutino per l'utente. Data: {today_str}.
Sii conciso, usa emoji per leggibilita. Non usare markdown, solo testo semplice con <b> e <i>.
Inizia con un saluto del mattino personalizzato.

DATI:
{raw_data}

Scrivi il briefing in italiano."""
        else:
            digest_prompt = f"""Genera un riepilogo serale per l'utente. Data: {today_str}.
Sii conciso, usa emoji per leggibilita. Non usare markdown, solo testo semplice con <b> e <i>.
Includi una preview dell'agenda di domani.

DATI:
{raw_data}

Scrivi il riepilogo in italiano."""

        digest = await gemini.generate(
            digest_prompt,
            model="gemini-2.5-flash",
            temperature=0.4,
        )

        # Send notification
        emoji = "🌅" if briefing_type == "morning" else "🌙"
        title = f"{emoji} Briefing {'mattutino' if briefing_type == 'morning' else 'serale'}"
        await notifier.notify_task_completed(user_id, title, digest)

        # Reschedule next briefing
        await self._schedule_next_briefing(user_id, briefing_type)

        return {
            "type": "daily_briefing",
            "briefing_type": briefing_type,
            "sections_count": len(sections),
            "delivered": True,
        }

    async def _schedule_next_briefing(self, user_id: str, current_type: str):
        """Schedule the next briefing (morning after evening, evening after morning)."""
        tz = ZoneInfo(settings.briefing_timezone)
        now_utc = datetime.utcnow()
        now_local = now_utc.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)

        if current_type == "morning":
            # Schedule evening briefing for today
            next_local = now_local.replace(
                hour=settings.briefing_evening_hour,
                minute=settings.briefing_evening_minute,
                second=0, microsecond=0
            )
            next_type = "evening"
            # If evening time already passed, schedule for tomorrow
            if next_local <= now_local:
                next_local += timedelta(days=1)
        else:
            # Schedule morning briefing for tomorrow
            next_local = (now_local + timedelta(days=1)).replace(
                hour=settings.briefing_morning_hour,
                minute=settings.briefing_morning_minute,
                second=0, microsecond=0
            )
            next_type = "morning"

        next_utc = next_local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)

        try:
            await TaskRepository.enqueue(
                user_id=user_id,
                task_type="daily_briefing",
                payload={"briefing_type": next_type},
                scheduled_at=next_utc,
                priority=9,
            )
            logger.info(f"Next {next_type} briefing scheduled for {next_utc.isoformat()} UTC")
        except Exception as e:
            logger.error(f"Failed to schedule next briefing: {e}")
```

**Step 4: Verify syntax**

Run: `cd /home/ubuntu/ai-agents && python -c "from jarvis.worker.executor import executor; print('OK')"`
Expected: `OK`

**Step 5: Commit**

```bash
git add src/jarvis/worker/executor.py
git commit -m "feat: add daily briefing handler (morning + evening)"
```

---

### Task 1.3: Add briefing initialization at worker boot

**Files:**
- Modify: `src/jarvis/worker/main.py`

**Step 1: Add init method to Worker class**

Add this method after `__init__` (line 27):

```python
    async def _init_scheduled_tasks(self):
        """Initialize recurring scheduled tasks if not already queued."""
        if not settings.briefing_user_id:
            logger.info("No BRIEFING_USER_ID configured, skipping briefing init")
            return

        # Check if a daily_briefing task already exists (pending or claimed)
        from jarvis.db.supabase_client import get_db, run_db
        db = get_db()
        existing = await run_db(lambda: db.table("task_queue")
            .select("id")
            .eq("task_type", "daily_briefing")
            .in_("status", ["pending", "claimed", "running"])
            .limit(1)
            .execute()
        )

        if existing.data:
            logger.info("Daily briefing already scheduled, skipping init")
            return

        # Schedule next briefing
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(settings.briefing_timezone)
        now_local = datetime.utcnow().replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)

        # Determine next briefing slot
        morning = now_local.replace(
            hour=settings.briefing_morning_hour,
            minute=settings.briefing_morning_minute,
            second=0, microsecond=0
        )
        evening = now_local.replace(
            hour=settings.briefing_evening_hour,
            minute=settings.briefing_evening_minute,
            second=0, microsecond=0
        )

        if now_local < morning:
            next_time = morning
            next_type = "morning"
        elif now_local < evening:
            next_time = evening
            next_type = "evening"
        else:
            next_time = morning + timedelta(days=1)
            next_type = "morning"

        next_utc = next_time.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)

        await TaskRepository.enqueue(
            user_id=settings.briefing_user_id,
            task_type="daily_briefing",
            payload={"briefing_type": next_type},
            scheduled_at=next_utc,
            priority=9,
        )
        logger.info(f"Initialized daily briefing: {next_type} at {next_utc.isoformat()} UTC")
```

**Step 2: Add import for timedelta at top**

Add `timedelta` to the datetime import line:

```python
from datetime import datetime, timedelta
```

**Step 3: Call init in `start()` method**

In the `start` method, after the signal handlers setup (after line 42), add:

```python
        # Initialize scheduled tasks
        await self._init_scheduled_tasks()
```

**Step 4: Verify syntax**

Run: `cd /home/ubuntu/ai-agents && python -c "from jarvis.worker.main import Worker; print('OK')"`
Expected: `OK`

**Step 5: Commit**

```bash
git add src/jarvis/worker/main.py
git commit -m "feat: auto-init daily briefing on worker boot"
```

---

## Feature 2: Email Monitoring

### Task 2.1: Implement email monitor handler

**Files:**
- Modify: `src/jarvis/worker/executor.py`

**Context:** Uses Redis to track last check timestamp. Filters emails by KG presence and urgency keywords.

**Step 1: Implement `_handle_email_monitor` method**

Add this method to `TaskExecutor` class, after `_handle_daily_briefing`:

```python
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

        # Get last check timestamp from Redis
        redis_key = f"email_monitor:last_check:{user_id}"
        last_check = await redis_client.get(redis_key)
        last_check_ts = last_check if last_check else None

        try:
            gmail = GmailClient()

            # Build query for new unread emails
            query = "is:unread"
            if last_check_ts:
                # Gmail accepts "after:YYYY/MM/DD" or epoch seconds
                query += f" after:{int(last_check_ts)}"

            emails = gmail.get_inbox(
                max_results=20,
                query=query,
                fetch_full_details=False
            )

            if not emails:
                # No new emails, just reschedule
                await redis_client.set(
                    redis_key,
                    int(datetime.utcnow().timestamp()),
                    ttl=86400 * 7  # Keep for 7 days
                )
                await self._reschedule_email_monitor(user_id, RESCHEDULE_MINUTES)
                return {"type": "email_monitor", "new_emails": 0, "notified": False}

            # Filter for important emails
            important_emails = []

            for email in emails:
                sender = email.get("from", "")
                subject = email.get("subject", "")
                snippet = email.get("snippet", "")
                is_important = False
                reason = ""

                # Check 1: Sender in Knowledge Graph (known person)
                sender_name = re.sub(r"<.*?>", "", sender).strip()
                sender_email_match = re.search(r"<(.+?)>", sender)
                sender_email = sender_email_match.group(1) if sender_email_match else sender

                try:
                    entities = await knowledge_graph.search_entities(
                        sender_name[:50], limit=1, threshold=0.8
                    )
                    if entities:
                        is_important = True
                        reason = f"Contatto noto: {entities[0].get('name', sender_name)}"
                except Exception:
                    pass

                # Check 2: Urgency keywords in subject or snippet
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

            # Update last check timestamp
            await redis_client.set(
                redis_key,
                int(datetime.utcnow().timestamp()),
                ttl=86400 * 7
            )

            # Notify if important emails found
            notified = False
            if important_emails:
                gemini.set_user_context(user_id)

                email_list = "\n".join([
                    f"- Da: {e['from']} — Oggetto: {e['subject']} (motivo: {e['reason']})"
                    for e in important_emails
                ])

                digest_prompt = f"""Hai ricevuto {len(important_emails)} email importanti.
Genera una notifica breve e chiara in italiano. Usa <b> per enfasi. Non usare markdown.
Indica chi scrive, l'oggetto e perche e importante (contatto noto o keyword urgente).

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
            # Still reschedule even on error
            await self._reschedule_email_monitor(user_id, RESCHEDULE_MINUTES)
            return {"type": "email_monitor", "error": str(e)}

        # Reschedule
        await self._reschedule_email_monitor(user_id, RESCHEDULE_MINUTES)

        return {
            "type": "email_monitor",
            "total_new": len(emails),
            "important": len(important_emails) if 'important_emails' in dir() else 0,
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
```

**Step 2: Add import for timedelta at top of executor.py**

Make sure `timedelta` is imported. Add to existing import if not present:

```python
from datetime import datetime, timedelta
```

**Step 3: Verify syntax**

Run: `cd /home/ubuntu/ai-agents && python -c "from jarvis.worker.executor import executor; print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add src/jarvis/worker/executor.py
git commit -m "feat: add email monitor with smart filtering (KG + keywords)"
```

---

### Task 2.2: Add email monitor initialization at worker boot

**Files:**
- Modify: `src/jarvis/worker/main.py`

**Step 1: Add email monitor init to `_init_scheduled_tasks`**

After the briefing init block, add:

```python
        # Initialize email monitor if not already queued
        existing_email = await run_db(lambda: db.table("task_queue")
            .select("id")
            .eq("task_type", "email_monitor")
            .in_("status", ["pending", "claimed", "running"])
            .limit(1)
            .execute()
        )

        if not existing_email.data and settings.briefing_user_id:
            next_check = datetime.utcnow() + timedelta(minutes=1)  # Start soon
            await TaskRepository.enqueue(
                user_id=settings.briefing_user_id,
                task_type="email_monitor",
                payload={},
                scheduled_at=next_check,
                priority=7,
            )
            logger.info("Initialized email monitor")
```

**Step 2: Verify syntax**

Run: `cd /home/ubuntu/ai-agents && python -c "from jarvis.worker.main import Worker; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add src/jarvis/worker/main.py
git commit -m "feat: auto-init email monitor on worker boot"
```

---

## Feature 3: Multi-step Reasoning with Self-Correction

### Task 3.1: Extend JarvisState for multi-step

**Files:**
- Modify: `src/jarvis/core/state.py`

**Step 1: Add new fields to JarvisState**

Add these fields to `JarvisState` (after line 37):

```python
    # Multi-step reasoning
    plan_steps: list[dict]  # [{"agents": [...], "goal": "..."}, ...]
    current_step_index: int
    step_results: list[dict]  # Results from completed steps
    step_retry_count: int
    max_retries: int
    max_steps: int
```

**Step 2: Verify syntax**

Run: `cd /home/ubuntu/ai-agents && python -c "from jarvis.core.state import JarvisState; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add src/jarvis/core/state.py
git commit -m "feat: extend JarvisState with multi-step fields"
```

---

### Task 3.2: Update Planner for multi-step output

**Files:**
- Modify: `src/jarvis/core/planner.py`

**Step 1: Update PLANNER_PROMPT**

Replace the entire `PLANNER_PROMPT` constant with a new version that supports multi-step planning. The key changes:
- Output format changes from `{"agents": [...]}` to `{"steps": [{"agents": [...], "goal": "..."}]}`
- Add multi-step examples
- Keep backward compatibility (single step = same as before)

The new prompt should be:

```python
PLANNER_PROMPT = """Sei un planner che decide quali agenti attivare per rispondere alla richiesta dell'utente.
Puoi pianificare AZIONI SEQUENZIALI quando servono piu passaggi.

AGENTI DISPONIBILI:
{agent_descriptions}

REGOLE:
1. Analizza cosa l'utente sta chiedendo, CONSIDERANDO IL CONTESTO della conversazione recente
2. Seleziona SOLO gli agenti necessari
3. Se la richiesta e semplice conversazione (saluti, ringraziamenti), restituisci steps vuoto
4. Se serve UN SOLO passaggio (caso comune), restituisci UN singolo step
5. Se servono AZIONI SEQUENZIALI (output di un agente serve come input per un altro), usa PIU step
6. MASSIMO 3 step per richiesta
7. Se l'utente fa riferimento a qualcosa detto prima, USA IL CONTESTO

⚠️ REGOLA CRITICA - VERIFICA/CONTROLLA:
Quando l'utente chiede di VERIFICARE, CONTROLLARE, CONFERMARE qualcosa,
DEVI SEMPRE attivare l'agente corrispondente per recuperare i dati REALI.

QUANDO USARE MULTI-STEP:
- "cerca l'email di Marco e crea un evento" → step1: email (cerca), step2: calendar (crea con dati email)
- "controlla il calendario e manda un riassunto via email" → step1: calendar, step2: email
- "cerca info su X nel web e salvale nella knowledge base" → step1: web, step2: rag

QUANDO NON USARE MULTI-STEP (un singolo step basta):
- "cosa ho domani" → step1: calendar
- "controlla email e calendario" → step1: calendar + email (paralleli nello stesso step)
- "ciao come stai" → steps: []

ESEMPI:
- "ciao" → {{"steps": [], "reasoning": "conversazione"}}
- "cosa ho domani" → {{"steps": [{{"agents": ["calendar"], "goal": "recupera eventi di domani"}}], "reasoning": "query calendario"}}
- "controlla email e calendario" → {{"steps": [{{"agents": ["calendar", "email"], "goal": "recupera eventi e email"}}], "reasoning": "query parallela"}}
- "cerca l'email di Marco e crea un evento basato su quella" → {{"steps": [{{"agents": ["email"], "goal": "cerca email da Marco"}}, {{"agents": ["calendar"], "goal": "crea evento basato sui dati dell'email trovata"}}], "reasoning": "azione sequenziale: prima email poi calendario"}}

Rispondi SOLO con un JSON valido:
{{"steps": [{{"agents": ["agent1"], "goal": "descrizione obiettivo step"}}], "reasoning": "breve spiegazione"}}

{conversation_context}
RICHIESTA UTENTE ATTUALE:
{user_input}

JSON:"""
```

**Step 2: Update `Planner.plan` method**

Replace the `plan` method to return both agents list (backward-compat) and steps:

```python
    async def plan(self, user_input: str, user_id: str = None, history: list = None) -> tuple[list[str], list[dict]]:
        """
        Analyze user input and determine which agents are needed.

        Returns:
            Tuple of (flat agent list for backward compat, list of step dicts)
        """
        agent_descriptions = "\n".join([
            f"- {name}: {desc}" for name, desc in AGENT_CAPABILITIES.items()
        ])

        conversation_context = ""
        if history and len(history) > 0:
            recent = history[-4:]
            context_lines = ["CONTESTO CONVERSAZIONE RECENTE:"]
            for msg in recent:
                role = "Utente" if msg.__class__.__name__ == "HumanMessage" else "Assistente"
                content = msg.content[:200] + "..." if len(msg.content) > 200 else msg.content
                context_lines.append(f"{role}: {content}")
            conversation_context = "\n".join(context_lines) + "\n\n"

        prompt = PLANNER_PROMPT.format(
            agent_descriptions=agent_descriptions,
            user_input=user_input,
            conversation_context=conversation_context
        )

        try:
            if user_id:
                gemini.set_user_context(user_id)

            response = await gemini.generate(
                prompt,
                model=self.model,
                temperature=0.1
            )

            clean_response = response.strip()
            if clean_response.startswith("```"):
                clean_response = clean_response.split("```")[1]
                if clean_response.startswith("json"):
                    clean_response = clean_response[4:]
                clean_response = clean_response.strip()

            result = json.loads(clean_response)
            steps = result.get("steps", [])
            reasoning = result.get("reasoning", "")

            # Validate steps
            valid_steps = []
            all_agents = []
            for step in steps[:3]:  # Max 3 steps
                agents = [a for a in step.get("agents", []) if a in AGENT_CAPABILITIES]
                if agents:
                    valid_steps.append({
                        "agents": agents,
                        "goal": step.get("goal", "")
                    })
                    all_agents.extend(agents)

            # Deduplicate flat agent list
            unique_agents = list(dict.fromkeys(all_agents))

            logger.info(f"Planner decision: {len(valid_steps)} steps, agents={unique_agents} - {reasoning}")
            return unique_agents, valid_steps

        except json.JSONDecodeError as e:
            logger.warning(f"Planner JSON parse error: {e}, response: {response[:200]}")
            agents = self._fallback_extraction(response)
            # Fallback: single step
            steps = [{"agents": agents, "goal": ""}] if agents else []
            return agents, steps

        except Exception as e:
            logger.error(f"Planner error: {e}")
            return [], []
```

**Step 3: Verify syntax**

Run: `cd /home/ubuntu/ai-agents && python -c "from jarvis.core.planner import planner; print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add src/jarvis/core/planner.py
git commit -m "feat: update planner for multi-step output with sequential steps"
```

---

### Task 3.3: Update orchestrator for multi-step execution

**Files:**
- Modify: `src/jarvis/core/orchestrator.py`

This is the most complex change. The orchestrator needs:
1. Updated `analyze_intent` to handle new planner output
2. New `verify_result` node
3. New `replan_step` node
4. Modified graph with loop support

**Step 1: Update `analyze_intent` to use new planner output**

Replace the `analyze_intent` function:

```python
async def analyze_intent(state: JarvisState) -> JarvisState:
    """Analyze user intent and determine required agents using LLM planner."""
    user_input = state["current_input"]
    user_id = state["user_id"]
    messages = state.get("messages", [])

    history = messages[:-1] if len(messages) > 1 else []

    required_agents, plan_steps = await planner.plan(user_input, user_id, history=history)

    if required_agents:
        intent = "action"
    else:
        intent = "chitchat"

    logger.info(f"Planner: intent={intent}, agents={required_agents}, steps={len(plan_steps)}")

    return {
        **state,
        "intent": intent,
        "intent_confidence": 1.0,
        "required_agents": required_agents,
        "plan_steps": plan_steps,
        "current_step_index": 0,
        "step_results": [],
        "step_retry_count": 0,
        "max_retries": 2,
        "max_steps": 3,
    }
```

**Step 2: Add new node functions**

Add these functions after `execute_agents`:

```python
async def prepare_step(state: JarvisState) -> JarvisState:
    """Prepare the current step for execution."""
    steps = state.get("plan_steps", [])
    idx = state.get("current_step_index", 0)

    if idx >= len(steps):
        return state

    current_step = steps[idx]
    step_agents = current_step.get("agents", [])
    step_goal = current_step.get("goal", "")

    # If there are previous step results, enrich the input with them
    enriched = state.get("enriched_input", state["current_input"])
    prev_results = state.get("step_results", [])

    if prev_results:
        # Add previous step context to enriched input
        prev_context = "\n".join([
            f"[Risultato step {i+1}]: {r.get('summary', str(r.get('data', '')))[:500]}"
            for i, r in enumerate(prev_results)
        ])
        enriched = f"{enriched}\n\nCONTESTO DAI PASSAGGI PRECEDENTI:\n{prev_context}"

    logger.info(f"Preparing step {idx+1}/{len(steps)}: agents={step_agents}, goal={step_goal}")

    return {
        **state,
        "required_agents": step_agents,
        "enriched_input": enriched,
        "agent_results": {},  # Clear for new step
    }


async def verify_result(state: JarvisState) -> JarvisState:
    """Verify if the current step's result is satisfactory."""
    steps = state.get("plan_steps", [])
    idx = state.get("current_step_index", 0)
    agent_results = state.get("agent_results", {})

    if idx >= len(steps):
        return state

    current_step = steps[idx]
    step_goal = current_step.get("goal", "")

    # Check if any agent had errors
    has_errors = any(
        not r.get("success", False)
        for r in agent_results.values()
    )

    # Summarize results for passing to next step
    step_summary = {}
    for agent_name, result in agent_results.items():
        if result.get("success"):
            data = result.get("data")
            # Create concise summary
            if isinstance(data, dict):
                step_summary = {
                    "agent": agent_name,
                    "success": True,
                    "data": data,
                    "summary": str(data)[:500],
                }
            else:
                step_summary = {
                    "agent": agent_name,
                    "success": True,
                    "data": data,
                    "summary": str(data)[:500] if data else "",
                }
        else:
            step_summary = {
                "agent": agent_name,
                "success": False,
                "error": result.get("error", "Unknown error"),
                "summary": f"Errore: {result.get('error', 'Unknown')}",
            }

    # Add to step results
    new_step_results = list(state.get("step_results", []))
    new_step_results.append(step_summary)

    if has_errors:
        logger.warning(f"Step {idx+1} had errors, retry_count={state.get('step_retry_count', 0)}")
    else:
        logger.info(f"Step {idx+1} completed successfully")

    return {
        **state,
        "step_results": new_step_results,
    }


async def replan_step(state: JarvisState) -> JarvisState:
    """Replan the current step after a failure."""
    steps = state.get("plan_steps", [])
    idx = state.get("current_step_index", 0)
    retry_count = state.get("step_retry_count", 0)

    if idx >= len(steps):
        return state

    current_step = steps[idx]
    error_info = state.get("step_results", [])[-1] if state.get("step_results") else {}

    logger.info(f"Replanning step {idx+1}, attempt {retry_count + 1}")

    # Ask planner for alternative approach
    error_msg = error_info.get("error", "Unknown error")
    original_goal = current_step.get("goal", "")

    try:
        replan_prompt = f"""L'azione precedente e fallita.
Obiettivo: {original_goal}
Errore: {error_msg}
Agenti usati: {current_step.get('agents', [])}

Suggerisci un approccio alternativo. Rispondi con JSON:
{{"agents": ["agent1"], "goal": "nuovo approccio"}}"""

        response = await gemini.generate(
            replan_prompt,
            system_instruction="Sei un planner. Rispondi SOLO con JSON valido.",
            model="gemini-2.5-flash",
            temperature=0.2
        )

        import json
        clean = response.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
            clean = clean.strip()

        new_plan = json.loads(clean)
        new_agents = [a for a in new_plan.get("agents", []) if a in AGENTS]

        if new_agents:
            # Update current step with new plan
            new_steps = list(steps)
            new_steps[idx] = {
                "agents": new_agents,
                "goal": new_plan.get("goal", original_goal)
            }
            # Remove the failed result so we get a clean retry
            new_results = list(state.get("step_results", []))
            if new_results:
                new_results.pop()

            return {
                **state,
                "plan_steps": new_steps,
                "step_results": new_results,
                "step_retry_count": retry_count + 1,
            }

    except Exception as e:
        logger.warning(f"Replan failed: {e}")

    # If replan fails, just increment retry to eventually bail out
    return {
        **state,
        "step_retry_count": retry_count + 1,
    }


def should_continue_steps(state: JarvisState) -> str:
    """Decide whether to continue to next step, retry, or generate response."""
    steps = state.get("plan_steps", [])
    idx = state.get("current_step_index", 0)
    step_results = state.get("step_results", [])
    retry_count = state.get("step_retry_count", 0)
    max_retries = state.get("max_retries", 2)

    # Check if last step had errors
    last_result = step_results[-1] if step_results else {}
    has_error = not last_result.get("success", True)

    if has_error and retry_count < max_retries:
        return "retry_step"

    if idx + 1 < len(steps) and not has_error:
        return "next_step"

    return "generate_response"


def advance_step(state: JarvisState) -> JarvisState:
    """Move to the next step."""
    return {
        **state,
        "current_step_index": state.get("current_step_index", 0) + 1,
        "step_retry_count": 0,  # Reset retry count for new step
    }
```

**Step 3: Update `build_graph` for multi-step loop**

Replace the `build_graph` function:

```python
def build_graph() -> StateGraph:
    """Build the Jarvis orchestrator graph with multi-step support."""
    graph = StateGraph(JarvisState)

    # Add nodes
    graph.add_node("analyze_intent", analyze_intent)
    graph.add_node("load_memory", load_memory)
    graph.add_node("prepare_step", prepare_step)
    graph.add_node("enrich_query", enrich_query)
    graph.add_node("check_freshness", check_freshness)
    graph.add_node("execute_agents", execute_agents)
    graph.add_node("verify_result", verify_result)
    graph.add_node("replan_step", replan_step)
    graph.add_node("advance_step", advance_step)
    graph.add_node("generate_response", generate_response)
    graph.add_node("extract_facts", extract_facts)

    # Set entry point
    graph.set_entry_point("analyze_intent")

    # Main flow
    graph.add_edge("analyze_intent", "load_memory")
    graph.add_conditional_edges(
        "load_memory",
        should_use_agents,
        {
            "use_agents": "prepare_step",
            "direct_response": "generate_response"
        }
    )

    # Step execution flow
    graph.add_edge("prepare_step", "enrich_query")
    graph.add_edge("enrich_query", "check_freshness")
    graph.add_edge("check_freshness", "execute_agents")
    graph.add_edge("execute_agents", "verify_result")

    # After verification: continue, retry, or respond
    graph.add_conditional_edges(
        "verify_result",
        should_continue_steps,
        {
            "next_step": "advance_step",
            "retry_step": "replan_step",
            "generate_response": "generate_response",
        }
    )

    # Loop back
    graph.add_edge("advance_step", "prepare_step")
    graph.add_edge("replan_step", "prepare_step")

    # Final
    graph.add_edge("generate_response", "extract_facts")
    graph.add_edge("extract_facts", END)

    return graph.compile()
```

**Step 4: Update `process_message` to include new state fields**

Update the `initial_state` dict in `process_message` to include the new fields:

After `"response_generated": False` add:

```python
        "plan_steps": [],
        "current_step_index": 0,
        "step_results": [],
        "step_retry_count": 0,
        "max_retries": 2,
        "max_steps": 3,
```

**Step 5: Update `generate_response` to include step results**

In the `generate_response` function, after formatting agent_data_str (around line 340), add step results context:

```python
    # Add multi-step context if applicable
    step_results = state.get("step_results", [])
    if len(step_results) > 1:
        # Multi-step execution happened, add all step results
        steps_str = "\n".join([
            f"[STEP {i+1}] {r.get('summary', 'N/A')}"
            for i, r in enumerate(step_results)
        ])
        agent_data_str = f"{steps_str}\n{agent_data_str}"
```

**Step 6: Verify syntax**

Run: `cd /home/ubuntu/ai-agents && python -c "from jarvis.core.orchestrator import process_message; print('OK')"`
Expected: `OK`

**Step 7: Commit**

```bash
git add src/jarvis/core/orchestrator.py
git commit -m "feat: multi-step reasoning with verify/replan loop in orchestrator"
```

---

### Task 3.4: Integration test for backward compatibility

**Files:**
- Modify: `tests/test_orchestrator.py`

**Step 1: Add backward compatibility test**

This test verifies that single-step queries still work after the multi-step changes:

```python
@pytest.mark.asyncio
async def test_single_step_backward_compat():
    """Verify single-step queries still work with new multi-step pipeline."""
    response = await process_message("test_user", "che tempo fa a Roma")
    assert response is not None
    assert len(response) > 0
```

**Step 2: Run tests**

Run: `cd /home/ubuntu/ai-agents && python -m pytest tests/test_orchestrator.py -v`
Expected: All tests pass

**Step 3: Commit**

```bash
git add tests/test_orchestrator.py
git commit -m "test: add backward compatibility test for multi-step orchestrator"
```

---

## Final: Set BRIEFING_USER_ID in .env

### Task 4.1: Configure environment

**Step 1: Add BRIEFING_USER_ID to .env**

The user needs to set their Telegram chat_id as `BRIEFING_USER_ID` in the `.env` file.
This is the same ID used as `user_id` in conversations (the Telegram chat_id).

Check what ID is used by looking at existing tasks or telegram config.

**Step 2: Restart worker**

After configuring, restart the worker to initialize the new scheduled tasks.

---

## Summary of all changes

| File | Change |
|------|--------|
| `src/jarvis/config.py` | Add briefing schedule settings |
| `src/jarvis/core/state.py` | Add multi-step fields to JarvisState |
| `src/jarvis/core/planner.py` | New prompt + multi-step output format |
| `src/jarvis/core/orchestrator.py` | New nodes (prepare_step, verify_result, replan_step, advance_step, should_continue_steps), updated graph with loop |
| `src/jarvis/worker/executor.py` | Add daily_briefing + email_monitor handlers |
| `src/jarvis/worker/main.py` | Auto-init briefing + email monitor on boot |
| `tests/test_orchestrator.py` | Backward compat test |
