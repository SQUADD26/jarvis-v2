"""Calendar agent - LLM-powered with tool calling."""

from datetime import datetime, timedelta
from typing import Any
import json
import asyncio
from jarvis.agents.base import BaseAgent
from jarvis.core.state import JarvisState
from jarvis.integrations.google_calendar import calendar_client
from jarvis.integrations.gemini import gemini
from jarvis.integrations.openai_embeddings import openai_embeddings
from jarvis.db.kg_repository import KGEntityRepository, KGAliasRepository
from jarvis.db.redis_client import redis_client

# Confirmation phrases that indicate user wants to proceed with pending action
CONFIRMATION_PHRASES = {"sì", "si", "yes", "ok", "procedi", "vai", "conferma", "fallo", "proceed", "confermo"}

# Tool definitions for the LLM
CALENDAR_TOOLS = [
    {
        "name": "get_events",
        "description": "Recupera gli eventi del calendario in un periodo specifico",
        "parameters": {
            "start_date": "Data inizio in formato YYYY-MM-DD",
            "end_date": "Data fine in formato YYYY-MM-DD",
            "start_time": "Ora inizio opzionale in formato HH:MM (default: 00:00)",
            "end_time": "Ora fine opzionale in formato HH:MM (default: 23:59)"
        }
    },
    {
        "name": "search_events",
        "description": "Cerca eventi per titolo/keyword. Utile per trovare l'ID di un evento prima di modificarlo o eliminarlo.",
        "parameters": {
            "query": "Testo da cercare nel titolo dell'evento",
            "start_date": "Data inizio ricerca (default: oggi)",
            "end_date": "Data fine ricerca (default: +30 giorni)"
        }
    },
    {
        "name": "create_event",
        "description": "Crea un nuovo evento nel calendario. Può invitare partecipanti e aggiungere Google Meet. Supporta eventi multi-giorno.",
        "parameters": {
            "title": "Titolo dell'evento (se non specificato, inferisci dal contesto es. 'Meeting con Mario')",
            "start_date": "Data inizio in formato YYYY-MM-DD",
            "end_date": "Data fine in formato YYYY-MM-DD (opzionale, se diversa da start_date per eventi multi-giorno)",
            "start_time": "Ora inizio in formato HH:MM",
            "end_time": "Ora fine in formato HH:MM (se non specificata, aggiungi 1 ora a start_time)",
            "description": "Descrizione opzionale",
            "location": "Luogo opzionale",
            "attendees": "Lista email dei partecipanti separata da virgola (opzionale, es: 'mario@gmail.com,luigi@gmail.com')",
            "add_meet": "Se true, aggiunge automaticamente un link Google Meet (default: true se ci sono attendees)"
        }
    },
    {
        "name": "update_event",
        "description": "Modifica un evento esistente. Richiede l'event_id (usa search_events per trovarlo).",
        "parameters": {
            "event_id": "ID dell'evento da modificare",
            "title": "Nuovo titolo (opzionale)",
            "date": "Nuova data in formato YYYY-MM-DD (opzionale)",
            "start_time": "Nuova ora inizio in formato HH:MM (opzionale)",
            "end_time": "Nuova ora fine in formato HH:MM (opzionale)",
            "description": "Nuova descrizione (opzionale)",
            "location": "Nuovo luogo (opzionale)"
        }
    },
    {
        "name": "delete_event",
        "description": "Elimina un evento dal calendario. Richiede l'event_id (usa search_events per trovarlo).",
        "parameters": {
            "event_id": "ID dell'evento da eliminare"
        }
    },
    {
        "name": "find_free_slots",
        "description": "Trova slot liberi nel calendario",
        "parameters": {
            "duration_minutes": "Durata richiesta in minuti",
            "start_date": "Data inizio ricerca in formato YYYY-MM-DD",
            "end_date": "Data fine ricerca in formato YYYY-MM-DD"
        }
    }
]

AGENT_SYSTEM_PROMPT = """Sei un agente calendario intelligente. Capisci le richieste dell'utente e chiami i tool appropriati.

OGGI: {today}
GIORNO DELLA SETTIMANA: {weekday}

TOOL DISPONIBILI:
{tools}

🧠 SII FURBO - INFERISCI E AGISCI, MAI CHIEDERE:
⚠️ NON CHIEDERE MAI CONFERME! Usa i default e agisci subito.

DURATA (OBBLIGATORIO - USA SEMPRE QUESTI DEFAULT):
- "1h", "un'ora" → end_time = start_time + 1 ora
- "30 min", "mezz'ora" → end_time = start_time + 30 min
- NESSUNA DURATA SPECIFICATA → USA 1 ORA DI DEFAULT (end_time = start_time + 1 ora)
- MAI chiedere "quanto dura?" - USA IL DEFAULT!

DATA (OBBLIGATORIO):
- Nessuna data specificata + ora futura oggi → usa {today}
- Nessuna data specificata + ora passata oggi → usa {tomorrow}
- "domani", "tomorrow" → {tomorrow}

PARTECIPANTI:
- "con mario@email.com" → attendee, titolo "Meeting con Mario"
- Email presente → add_meet = true automaticamente
- "call", "videocall", "meeting online" → add_meet = true

📧 GESTIONE PARTECIPANTI:
- Estrai email da frasi tipo "con tizio@gmail.com" o "invita caio@email.it"
- Se l'utente fornisce solo nome, NON inventare email
- Più email separate da virgola: "mario@x.com,luigi@y.com"

📅 REGOLE DATE:
- "domani" = {tomorrow}
- "oggi" = {today}
- "lunedì prossimo" = calcola la data corretta
- Se l'utente parla al futuro senza data, usa {tomorrow}

⚠️ MODIFICHE/ELIMINAZIONI - WORKFLOW OBBLIGATORIO:
- "spostalo", "cambia orario", "modifica", "elimina" → RESTITUISCI ARRAY con 2 operazioni:
  1. search_events per trovare l'evento
  2. update_event o delete_event con event_id: "FOUND_EVENT_ID" (placeholder)
- Il sistema eseguirà search prima, poi sostituirà il placeholder con l'ID reale
- "sistema", "correggi", "elimina duplicati" → PRIMA fai get_events per vedere cosa c'è

⚠️ EVITA DUPLICATI:
- Ogni operazione UNA SOLA VOLTA
- "appuntamento alle 10 e alle 14" = ESATTAMENTE 2 create_event
- NON ripetere la stessa operazione

📝 OUTPUT FORMAT:
Rispondi SOLO con JSON valido:
- Singola: {{"tool": "nome", "params": {{...}}}}
- Multiple: [{{"tool": "...", "params": {{...}}}}, ...]

ESEMPI (NOTA: mai chiedere conferme, usa i default):
- "agenda domani" → {{"tool": "get_events", "params": {{"start_date": "{tomorrow}", "end_date": "{tomorrow}"}}}}
- "evento alle 12 con test@gmail.com" → {{"tool": "create_event", "params": {{"title": "Meeting con Test", "start_date": "{today}", "start_time": "12:00", "end_time": "13:00", "attendees": "test@gmail.com", "add_meet": true}}}}
  ↑ NOTA: nessuna durata specificata = 1 ora di default (12:00-13:00)
- "bloccami giovedì 15-17" → {{"tool": "create_event", "params": {{"title": "Occupato", "start_date": "YYYY-MM-DD", "start_time": "15:00", "end_time": "17:00"}}}}
- "mettimi un evento alle 10" → {{"tool": "create_event", "params": {{"title": "Evento", "start_date": "{today}", "start_time": "10:00", "end_time": "11:00"}}}}
  ↑ NOTA: nessuna durata = 1 ora, nessun titolo specifico = "Evento"
- "blocca agenda da mercoledì 14 a sabato 20" → {{"tool": "create_event", "params": {{"title": "Occupato", "start_date": "2025-01-29", "end_date": "2025-02-01", "start_time": "14:00", "end_time": "20:00"}}}}
  ↑ NOTA: evento multi-giorno usa start_date e end_date DIVERSI
- "spostalo alle 13" (dopo aver creato "evento di test") → [{{"tool": "search_events", "params": {{"query": "evento di test"}}}}, {{"tool": "update_event", "params": {{"event_id": "FOUND_EVENT_ID", "start_time": "13:00", "end_time": "14:00"}}}}]
  ↑ NOTA: array con search + update. Il sistema sostituisce FOUND_EVENT_ID con l'ID reale
- "sposta X alle 14 e Y alle 17:30" → [{{"tool": "search_events", "params": {{"query": "X"}}}}, {{"tool": "update_event", "params": {{"event_id": "FOUND_EVENT_ID", "start_time": "14:00", "end_time": "15:00"}}}}, {{"tool": "search_events", "params": {{"query": "Y"}}}}, {{"tool": "update_event", "params": {{"event_id": "FOUND_EVENT_ID", "start_time": "17:30", "end_time": "18:30"}}}}]
  ↑ NOTA: per operazioni MULTIPLE su eventi DIVERSI, metti TUTTE le coppie search+update nell'array

Rispondi SOLO con il JSON, nient'altro."""

# Prompt for follow-up after getting search/get results
FOLLOWUP_PROMPT = """Sei un agente calendario. Hai appena eseguito una ricerca e questi sono i risultati.

⚠️ DATE IMPORTANTI - FAI ATTENZIONE:
- OGGI: {today}
- DOMANI: {tomorrow}
- GIORNO DELLA SETTIMANA: {weekday}

RICHIESTA ORIGINALE DELL'UTENTE:
{original_request}

RISULTATI DELLA RICERCA:
{search_results}

Ora, basandoti sui risultati, decidi quali operazioni eseguire.
Per eliminare o modificare eventi, usa gli event_id mostrati nei risultati.

TOOL DISPONIBILI:
{tools}

Rispondi SOLO con un JSON valido:
- Singola operazione: {{"tool": "nome_tool", "params": {{...}}}}
- Multiple operazioni: [{{"tool": "nome_tool", "params": {{...}}}}, ...]
- Nessuna azione necessaria: {{"tool": "none", "message": "spiegazione"}}

JSON:"""


class CalendarAgent(BaseAgent):
    name = "calendar"
    resource_type = None  # Disable caching - every request needs LLM interpretation

    async def _enrich_entities_from_events(self, user_id: str, events: list[dict]) -> None:
        """Extract person entities from calendar event attendees (background task)."""
        try:
            for event in events:
                attendees = event.get("attendees", [])
                event_title = event.get("title", "")
                event_id = event.get("id")

                for email in attendees:
                    if not email or "@" not in email:
                        continue

                    # Skip own email (usually ends with user's domain)
                    # Extract name from email if possible
                    local_part = email.split("@")[0]

                    # Convert email local part to name (e.g., "mario.rossi" -> "Mario Rossi")
                    name_parts = local_part.replace(".", " ").replace("_", " ").replace("-", " ").split()
                    canonical_name = " ".join(p.capitalize() for p in name_parts)

                    # Skip if name is too short or generic
                    if len(canonical_name) < 3 or canonical_name.lower() in ["info", "support", "admin", "noreply", "no-reply"]:
                        continue

                    # Generate embedding for the entity (OpenAI 3072-dim)
                    embedding = await openai_embeddings.embed(canonical_name)

                    # Try to create entity (will fail silently if exists)
                    entity = await KGEntityRepository.create_entity(
                        user_id=user_id,
                        canonical_name=canonical_name,
                        entity_type="person",
                        properties={"email": email, "source": "calendar"},
                        embedding=embedding,
                        confidence=0.6,  # Lower confidence from calendar extraction
                        source_type="calendar",
                        source_id=event_id
                    )

                    if entity:
                        # Add email as alias
                        await KGAliasRepository.add_alias(entity["id"], email, confidence=0.9)
                        # Add local part as alias
                        await KGAliasRepository.add_alias(entity["id"], local_part, confidence=0.7)
                        self.logger.debug(f"Created entity from calendar: {canonical_name}")
                    else:
                        # Entity already exists, try to update mention
                        existing = await KGEntityRepository.get_entity_by_name(user_id, canonical_name, "person")
                        if existing:
                            await KGEntityRepository.update_mention(existing["id"])
                            # Ensure email is added as alias
                            await KGAliasRepository.add_alias(existing["id"], email, confidence=0.9)

        except Exception as e:
            self.logger.warning(f"Failed to enrich entities from calendar: {e}")

    async def _save_pending_action(self, user_id: str, action: dict) -> None:
        """Save a pending action for later confirmation."""
        key = f"calendar_pending:{user_id}"
        await redis_client.set(key, json.dumps(action), ex=300)  # 5 min expiry
        self.logger.info(f"Saved pending action for {user_id}: {action.get('action')}")

    async def _get_pending_action(self, user_id: str) -> dict | None:
        """Get and clear pending action."""
        key = f"calendar_pending:{user_id}"
        data = await redis_client.get(key)
        if data:
            await redis_client.delete(key)
            return json.loads(data)
        return None

    def _is_confirmation(self, text: str) -> bool:
        """Check if user input is a confirmation."""
        return text.strip().lower() in CONFIRMATION_PHRASES

    async def _execute(self, state: JarvisState) -> Any:
        """Execute calendar operations using LLM reasoning."""
        user_input = state["current_input"]
        user_id = state["user_id"]
        messages = state.get("messages", [])
        self._current_user_id = user_id  # Store for tool methods

        # Check for pending action if user is confirming
        if self._is_confirmation(user_input):
            pending = await self._get_pending_action(user_id)
            if pending:
                self.logger.info(f"Executing pending action: {pending.get('action')}")
                if pending.get("action") == "update_event":
                    return await self._tool_update_event(pending.get("params", {}))
                elif pending.get("action") == "delete_event":
                    return await self._tool_delete_event(pending.get("params", {}))

        # Build conversation context from recent messages (for follow-up understanding)
        conversation_context = ""
        if len(messages) > 1:
            # Get last 4 messages for context (excluding current)
            recent = messages[-5:-1] if len(messages) > 5 else messages[:-1]
            context_parts = []
            for msg in recent:
                role = "Utente" if hasattr(msg, 'type') and msg.type == "human" else "Assistente"
                if hasattr(msg, 'content'):
                    context_parts.append(f"{role}: {msg.content}")
            if context_parts:
                conversation_context = "\n".join(context_parts)

        # Get current date info
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")
        weekday_names = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]
        weekday = weekday_names[now.weekday()]

        # Format tools for prompt
        tools_str = json.dumps(CALENDAR_TOOLS, indent=2, ensure_ascii=False)

        # Build prompt
        prompt = AGENT_SYSTEM_PROMPT.format(
            today=today,
            tomorrow=tomorrow,
            weekday=weekday,
            tools=tools_str
        )

        # Build full input with conversation context
        if conversation_context:
            full_input = f"""CONTESTO CONVERSAZIONE RECENTE:
{conversation_context}

RICHIESTA ATTUALE DELL'UTENTE:
{user_input}

IMPORTANTE: Se la richiesta attuale è una risposta/conferma a una domanda precedente (es. "1h", "sì", "ok"),
usa il contesto della conversazione per capire cosa l'utente vuole fare e completa l'azione."""
        else:
            full_input = user_input

        # Ask LLM what to do
        response = await gemini.generate(
            full_input,
            system_instruction=prompt,
            model="gemini-2.5-flash",
            temperature=0.1
        )

        # Parse LLM response
        try:
            clean_response = response.strip()
            if clean_response.startswith("```"):
                clean_response = clean_response.split("```")[1]
                if clean_response.startswith("json"):
                    clean_response = clean_response[4:]
                clean_response = clean_response.strip()

            decision = json.loads(clean_response)

            # Handle both single and multiple tool calls
            if isinstance(decision, list):
                # Check for search→update/delete pattern (sequential workflow)
                # Process pairs: (search, action), (search, action), ...
                results = []
                i = 0
                while i < len(decision) - 1:
                    first_tool = decision[i].get("tool")
                    second_tool = decision[i + 1].get("tool")

                    # Sequential workflow: search first, then update/delete with found ID
                    if first_tool in ("search_events", "get_events") and second_tool in ("update_event", "delete_event"):
                        self.logger.info(f"Calendar agent: sequential workflow {first_tool} → {second_tool}")

                        # Execute search first
                        search_params = decision[i].get("params", {})
                        self.logger.info(f"Calendar agent decision: {first_tool} with {search_params}")
                        search_result = await self._execute_tool(first_tool, search_params)

                        # Get event ID from search results
                        events = search_result.get("events", [])
                        if not events:
                            results.append({
                                "operation": "search_then_update",
                                "search_result": search_result,
                                "error": f"Nessun evento trovato per '{search_params.get('query', '')}'"
                            })
                            i += 2
                            continue

                        # Use first matching event's ID
                        found_event_id = events[0].get("id")
                        found_event_title = events[0].get("title", "evento")

                        # Replace placeholder in update/delete params
                        action_params = decision[i + 1].get("params", {}).copy()
                        if action_params.get("event_id") == "FOUND_EVENT_ID":
                            action_params["event_id"] = found_event_id

                        # Execute update/delete
                        self.logger.info(f"Calendar agent decision: {second_tool} with {action_params}")
                        action_result = await self._execute_tool(second_tool, action_params)

                        results.append({
                            "operation": f"search_then_{second_tool}",
                            "found_event": found_event_title,
                            "action_result": action_result
                        })
                        i += 2  # Move to next pair
                    else:
                        # Not a search→action pair, execute single tool
                        tool_name = decision[i].get("tool")
                        params = decision[i].get("params", {})
                        self.logger.info(f"Calendar agent decision: {tool_name} with {params}")
                        result = await self._execute_tool(tool_name, params)
                        results.append(result)
                        i += 1

                # Handle any remaining single tool at the end
                if i < len(decision):
                    tool_name = decision[i].get("tool")
                    params = decision[i].get("params", {})
                    self.logger.info(f"Calendar agent decision: {tool_name} with {params}")
                    result = await self._execute_tool(tool_name, params)
                    results.append(result)

                # Return results
                if len(results) == 1:
                    return results[0]
                return {"multiple_results": results}
            else:
                # Single tool call
                tool_name = decision.get("tool")
                params = decision.get("params", {})
                self.logger.info(f"Calendar agent decision: {tool_name} with {params}")
                return await self._execute_tool(tool_name, params)

        except Exception as e:
            self.logger.error(f"Failed to parse LLM response: {response[:200]}")
            return {"error": f"Non ho capito la richiesta: {str(e)}"}

    async def _execute_tool(self, tool_name: str, params: dict) -> dict:
        """Execute the selected tool with given parameters."""
        user_id = getattr(self, "_current_user_id", None)

        if tool_name == "get_events":
            return await self._tool_get_events(params, user_id)
        elif tool_name == "search_events":
            return await self._tool_search_events(params, user_id)
        elif tool_name == "create_event":
            return await self._tool_create_event(params)
        elif tool_name == "update_event":
            return await self._tool_update_event(params)
        elif tool_name == "delete_event":
            return await self._tool_delete_event(params)
        elif tool_name == "find_free_slots":
            return await self._tool_find_free_slots(params)
        else:
            return {"error": f"Tool sconosciuto: {tool_name}"}

    async def _tool_get_events(self, params: dict, user_id: str = None) -> dict:
        """Get calendar events."""
        try:
            start_date = params.get("start_date")
            end_date = params.get("end_date")
            start_time = params.get("start_time", "00:00")
            end_time = params.get("end_time", "23:59")

            start = datetime.fromisoformat(f"{start_date}T{start_time}")
            end = datetime.fromisoformat(f"{end_date}T{end_time}")

            events = calendar_client.get_events(start=start, end=end)

            # Enrich KG with attendees (background task)
            if events and user_id:
                asyncio.create_task(self._enrich_entities_from_events(user_id, events))

            return {
                "operation": "get_events",
                "period": f"{start_date} {start_time} - {end_date} {end_time}",
                "events": events,
                "count": len(events)
            }
        except Exception as e:
            self.logger.error(f"get_events failed: {e}")
            return {"error": f"Errore nel recupero eventi: {str(e)}"}

    async def _tool_search_events(self, params: dict, user_id: str = None) -> dict:
        """Search events by title/keyword."""
        try:
            query = params.get("query", "").lower()
            now = datetime.now()

            # Default search range: today to +30 days
            start_date = params.get("start_date", now.strftime("%Y-%m-%d"))
            end_date = params.get("end_date", (now + timedelta(days=30)).strftime("%Y-%m-%d"))

            start = datetime.fromisoformat(f"{start_date}T00:00")
            end = datetime.fromisoformat(f"{end_date}T23:59")

            # Get all events in range
            all_events = calendar_client.get_events(start=start, end=end, max_results=100)

            # Filter by query (search in title and description)
            matching = []
            for event in all_events:
                title = (event.get("title") or "").lower()
                description = (event.get("description") or "").lower()
                if query in title or query in description:
                    matching.append(event)

            # Enrich KG with attendees from matching events (background task)
            if matching and user_id:
                asyncio.create_task(self._enrich_entities_from_events(user_id, matching))

            return {
                "operation": "search_events",
                "query": query,
                "events": matching,
                "count": len(matching),
                "message": f"Trovati {len(matching)} eventi con '{query}'" if matching else f"Nessun evento trovato con '{query}'"
            }
        except Exception as e:
            self.logger.error(f"search_events failed: {e}")
            return {"error": f"Errore nella ricerca eventi: {str(e)}"}

    async def _tool_create_event(self, params: dict) -> dict:
        """Create a calendar event with optional attendees and Google Meet."""
        try:
            # Support both old 'date' param and new 'start_date'/'end_date' for multi-day
            start_date = params.get("start_date") or params.get("date")
            end_date = params.get("end_date") or start_date  # Default to same day if not specified
            start_time = params.get("start_time")
            end_time = params.get("end_time")
            title = params.get("title", "Nuovo evento")

            start = datetime.fromisoformat(f"{start_date}T{start_time}")
            end = datetime.fromisoformat(f"{end_date}T{end_time}")

            # Parse attendees (comma-separated string to list)
            attendees_raw = params.get("attendees", "")
            attendees = None
            if attendees_raw:
                attendees = [e.strip() for e in attendees_raw.split(",") if e.strip() and "@" in e]

            # Determine if we should add Google Meet
            add_meet_param = params.get("add_meet")
            if isinstance(add_meet_param, str):
                add_meet = add_meet_param.lower() == "true"
            elif isinstance(add_meet_param, bool):
                add_meet = add_meet_param
            else:
                # Default: add meet if there are attendees
                add_meet = bool(attendees)

            # Check for existing events at the same time to warn about potential conflicts
            existing_events = calendar_client.get_events(start=start, end=end)
            conflicts = []
            for ev in existing_events:
                # Check if there's an event with similar title at same time (potential duplicate)
                ev_title = (ev.get("title") or "").lower()
                if title.lower() in ev_title or ev_title in title.lower():
                    conflicts.append(ev)

            event = calendar_client.create_event(
                title=title,
                start=start,
                end=end,
                description=params.get("description"),
                location=params.get("location"),
                attendees=attendees,
                add_meet=add_meet
            )

            # Build response message
            if start_date == end_date:
                message = f"Evento '{event['title']}' creato per {start_date} {start_time}-{end_time}"
            else:
                message = f"Evento '{event['title']}' creato da {start_date} ore {start_time} a {end_date} ore {end_time}"
            if attendees:
                message += f" con {len(attendees)} partecipanti"
            if event.get("meet_link"):
                message += f"\n📹 Meet: {event['meet_link']}"

            result = {
                "operation": "create_event",
                "event": event,
                "message": message
            }

            if conflicts:
                self.logger.warning(f"Potential duplicate: {title} conflicts with {[c['title'] for c in conflicts]}")
                result["warning"] = f"⚠️ Attenzione: esistono già eventi simili in questo orario: {[c['title'] for c in conflicts]}"

            return result
        except Exception as e:
            self.logger.error(f"create_event failed: {e}")
            return {"error": f"Errore nella creazione evento: {str(e)}"}

    async def _tool_update_event(self, params: dict) -> dict:
        """Update an existing calendar event."""
        try:
            event_id = params.get("event_id")
            if not event_id:
                return {"error": "event_id mancante. Usa search_events per trovare l'ID dell'evento."}

            # Build updates dict
            updates = {}

            if params.get("title"):
                updates["title"] = params["title"]
            if params.get("description"):
                updates["description"] = params["description"]
            if params.get("location"):
                updates["location"] = params["location"]

            # Handle date/time updates
            date = params.get("date")
            start_time = params.get("start_time")
            end_time = params.get("end_time")

            if date and start_time:
                updates["start"] = datetime.fromisoformat(f"{date}T{start_time}")
            elif start_time:
                # If only time provided, we need to get current event date
                # For now, assume today if date not provided
                updates["start"] = datetime.fromisoformat(f"{datetime.now().strftime('%Y-%m-%d')}T{start_time}")

            if date and end_time:
                updates["end"] = datetime.fromisoformat(f"{date}T{end_time}")
            elif end_time:
                updates["end"] = datetime.fromisoformat(f"{datetime.now().strftime('%Y-%m-%d')}T{end_time}")

            if not updates:
                return {"error": "Nessuna modifica specificata"}

            event = calendar_client.update_event(event_id=event_id, updates=updates)

            return {
                "operation": "update_event",
                "event": event,
                "message": f"Evento '{event['title']}' aggiornato"
            }
        except Exception as e:
            self.logger.error(f"update_event failed: {e}")
            return {"error": f"Errore nell'aggiornamento evento: {str(e)}"}

    async def _tool_delete_event(self, params: dict) -> dict:
        """Delete a calendar event."""
        try:
            event_id = params.get("event_id")
            calendar_client.delete_event(event_id)

            return {
                "operation": "delete_event",
                "event_id": event_id,
                "message": "Evento eliminato"
            }
        except Exception as e:
            self.logger.error(f"delete_event failed: {e}")
            return {"error": f"Errore nell'eliminazione evento: {str(e)}"}

    async def _tool_find_free_slots(self, params: dict) -> dict:
        """Find free time slots."""
        try:
            duration = params.get("duration_minutes", 60)
            start_date = params.get("start_date")
            end_date = params.get("end_date")

            start = datetime.fromisoformat(f"{start_date}T00:00")
            end = datetime.fromisoformat(f"{end_date}T23:59")

            slots = calendar_client.find_free_slots(
                duration_minutes=duration,
                start=start,
                end=end
            )

            return {
                "operation": "find_free_slots",
                "duration_minutes": duration,
                "slots": slots,
                "count": len(slots)
            }
        except Exception as e:
            self.logger.error(f"find_free_slots failed: {e}")
            return {"error": f"Errore nella ricerca slot: {str(e)}"}


# Singleton
calendar_agent = CalendarAgent()
