"""Calendar agent - LLM-powered with intelligent two-step workflow."""

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

# Tool definitions for the LLM
CALENDAR_TOOLS = [
    {
        "name": "get_events",
        "description": "Recupera gli eventi del calendario in un periodo specifico. USA QUESTO quando conosci la data dell'evento.",
        "parameters": {
            "start_date": "Data inizio in formato YYYY-MM-DD",
            "end_date": "Data fine in formato YYYY-MM-DD",
        }
    },
    {
        "name": "search_events",
        "description": "Cerca eventi per titolo/keyword. USA QUESTO solo se NON conosci la data.",
        "parameters": {
            "query": "Testo da cercare nel titolo dell'evento",
            "start_date": "Data inizio ricerca (default: oggi)",
            "end_date": "Data fine ricerca (default: +30 giorni)"
        }
    },
    {
        "name": "create_event",
        "description": "Crea un nuovo evento. Supporta eventi multi-giorno.",
        "parameters": {
            "title": "Titolo dell'evento",
            "start_date": "Data inizio in formato YYYY-MM-DD",
            "end_date": "Data fine in formato YYYY-MM-DD (opzionale, per eventi multi-giorno)",
            "start_time": "Ora inizio in formato HH:MM",
            "end_time": "Ora fine in formato HH:MM",
            "description": "Descrizione opzionale",
            "location": "Luogo opzionale",
            "attendees": "Email partecipanti separati da virgola (opzionale)",
            "add_meet": "true per aggiungere Google Meet"
        }
    },
    {
        "name": "update_event",
        "description": "Modifica un evento esistente. RICHIEDE event_id reale (non placeholder).",
        "parameters": {
            "event_id": "ID dell'evento (es: 'abc123xyz')",
            "title": "Nuovo titolo (opzionale)",
            "start_date": "Nuova data inizio (opzionale)",
            "end_date": "Nuova data fine (opzionale)",
            "start_time": "Nuova ora inizio (opzionale)",
            "end_time": "Nuova ora fine (opzionale)"
        }
    },
    {
        "name": "delete_event",
        "description": "Elimina un evento. RICHIEDE event_id reale (non placeholder).",
        "parameters": {
            "event_id": "ID dell'evento da eliminare (es: 'abc123xyz')"
        }
    },
    {
        "name": "find_free_slots",
        "description": "Trova slot liberi nel calendario",
        "parameters": {
            "duration_minutes": "Durata richiesta in minuti",
            "start_date": "Data inizio ricerca",
            "end_date": "Data fine ricerca"
        }
    }
]

AGENT_SYSTEM_PROMPT = """Sei un agente calendario INTELLIGENTE. Analizza le richieste e usa i tool appropriati.

OGGI: {today} ({weekday})
DOMANI: {tomorrow}

TOOL DISPONIBILI:
{tools}

🧠 REGOLE FONDAMENTALI:

1. CREAZIONE EVENTI - Agisci subito, non chiedere conferme:
   - Nessuna durata specificata → 1 ora di default
   - Nessun titolo → "Evento" o inferisci dal contesto
   - "da lunedì a giovedì" → usa start_date e end_date DIVERSI
   - Email presente → add_meet = true

2. MODIFICA/ELIMINAZIONE - HAI BISOGNO DELL'event_id:
   - Se NON hai l'event_id, devi PRIMA recuperare gli eventi
   - Se conosci la DATA → usa get_events per quella data
   - Se NON conosci la data → usa search_events
   - Restituisci SOLO il tool di ricerca, il sistema ti mostrerà i risultati

3. QUANDO RESTITUIRE SOLO get_events o search_events:
   - "cancella l'evento X" → get_events o search_events (per trovare l'ID)
   - "sposta l'appuntamento di domani" → get_events per domani
   - "elimina il meeting delle 10" → get_events per oggi
   - Il sistema ti richiamerà con i risultati e potrai scegliere l'evento giusto

📅 DATE:
- "oggi" = {today}
- "domani" = {tomorrow}
- "lunedì prossimo" = calcola la data
- "2 febbraio" = 2026-02-02

📝 OUTPUT: Solo JSON valido
- Singola: {{"tool": "nome", "params": {{...}}}}
- Multiple (solo per create_event multipli): [{{"tool": "create_event", ...}}, ...]

ESEMPI:
- "agenda domani" → {{"tool": "get_events", "params": {{"start_date": "{tomorrow}", "end_date": "{tomorrow}"}}}}
- "crea evento alle 15" → {{"tool": "create_event", "params": {{"title": "Evento", "start_date": "{today}", "start_time": "15:00", "end_time": "16:00"}}}}
- "blocca da mercoledì 14 a sabato 20" → {{"tool": "create_event", "params": {{"title": "Occupato", "start_date": "2026-01-29", "end_date": "2026-02-01", "start_time": "14:00", "end_time": "20:00"}}}}
- "cancella l'evento vertua di lunedì 2 febbraio" → {{"tool": "get_events", "params": {{"start_date": "2026-02-02", "end_date": "2026-02-02"}}}}
  (poi vedrai gli eventi e potrai eliminare quello giusto)
- "elimina il pranzo di domani" → {{"tool": "get_events", "params": {{"start_date": "{tomorrow}", "end_date": "{tomorrow}"}}}}
- "sposta il meeting X alle 14" → {{"tool": "search_events", "params": {{"query": "X"}}}}

Rispondi SOLO con JSON."""

# Prompt for second step - after getting events
FOLLOWUP_PROMPT = """Hai chiesto gli eventi e questi sono i risultati.

OGGI: {today} ({weekday})
RICHIESTA ORIGINALE: {original_request}

EVENTI TROVATI:
{events_list}

Ora scegli l'evento corretto e esegui l'azione richiesta.
Usa l'event_id REALE mostrato sopra (NON inventare ID, NON usare placeholder).

TOOL DISPONIBILI:
{tools}

Se l'utente voleva:
- Eliminare → {{"tool": "delete_event", "params": {{"event_id": "ID_REALE_QUI"}}}}
- Modificare → {{"tool": "update_event", "params": {{"event_id": "ID_REALE_QUI", ...}}}}
- Solo vedere → {{"tool": "none", "message": "Ecco gli eventi"}}

Se ci sono PIÙ eventi che potrebbero corrispondere, scegli quello più probabile basandoti su:
- Titolo (quale assomiglia di più alla richiesta?)
- Orario (se l'utente ha menzionato un'ora)
- Contesto della conversazione

Rispondi SOLO con JSON."""


class CalendarAgent(BaseAgent):
    name = "calendar"
    resource_type = None  # Disable caching

    async def _enrich_entities_from_events(self, user_id: str, events: list[dict]) -> None:
        """Extract person entities from calendar event attendees (background task)."""
        try:
            for event in events:
                attendees = event.get("attendees", [])
                event_id = event.get("id")

                for email in attendees:
                    if not email or "@" not in email:
                        continue

                    local_part = email.split("@")[0]
                    name_parts = local_part.replace(".", " ").replace("_", " ").replace("-", " ").split()
                    canonical_name = " ".join(p.capitalize() for p in name_parts)

                    if len(canonical_name) < 3 or canonical_name.lower() in ["info", "support", "admin", "noreply"]:
                        continue

                    embedding = await openai_embeddings.embed(canonical_name)
                    entity = await KGEntityRepository.create_entity(
                        user_id=user_id,
                        canonical_name=canonical_name,
                        entity_type="person",
                        properties={"email": email, "source": "calendar"},
                        embedding=embedding,
                        confidence=0.6,
                        source_type="calendar",
                        source_id=event_id
                    )

                    if entity:
                        await KGAliasRepository.add_alias(entity["id"], email, confidence=0.9)
                        await KGAliasRepository.add_alias(entity["id"], local_part, confidence=0.7)
                    else:
                        existing = await KGEntityRepository.get_entity_by_name(user_id, canonical_name, "person")
                        if existing:
                            await KGEntityRepository.update_mention(existing["id"])
                            await KGAliasRepository.add_alias(existing["id"], email, confidence=0.9)

        except Exception as e:
            self.logger.warning(f"Failed to enrich entities: {e}")

    def _format_events_for_llm(self, events: list[dict]) -> str:
        """Format events list for LLM consumption with clear IDs."""
        if not events:
            return "Nessun evento trovato."

        lines = []
        for ev in events:
            event_id = ev.get("id", "???")
            title = ev.get("title", "Senza titolo")
            start = ev.get("start", "")
            end = ev.get("end", "")

            # Format datetime nicely
            if isinstance(start, str) and "T" in start:
                start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                start_str = start_dt.strftime("%d/%m %H:%M")
            else:
                start_str = str(start)

            if isinstance(end, str) and "T" in end:
                end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
                end_str = end_dt.strftime("%H:%M")
            else:
                end_str = str(end)

            lines.append(f"- [{event_id}] \"{title}\" ({start_str}-{end_str})")

        return "\n".join(lines)

    async def _execute(self, state: JarvisState) -> Any:
        """Execute calendar operations with intelligent two-step workflow."""
        user_input = state["current_input"]
        user_id = state["user_id"]
        messages = state.get("messages", [])
        self._current_user_id = user_id

        # Build conversation context
        conversation_context = ""
        if len(messages) > 1:
            recent = messages[-5:-1] if len(messages) > 5 else messages[:-1]
            context_parts = []
            for msg in recent:
                role = "Utente" if hasattr(msg, 'type') and msg.type == "human" else "Assistente"
                if hasattr(msg, 'content'):
                    context_parts.append(f"{role}: {msg.content}")
            if context_parts:
                conversation_context = "\n".join(context_parts)

        # Date info
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")
        weekday_names = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]
        weekday = weekday_names[now.weekday()]

        tools_str = json.dumps(CALENDAR_TOOLS, indent=2, ensure_ascii=False)

        # Build prompt
        prompt = AGENT_SYSTEM_PROMPT.format(
            today=today,
            tomorrow=tomorrow,
            weekday=weekday,
            tools=tools_str
        )

        # Build input with context
        if conversation_context:
            full_input = f"CONTESTO:\n{conversation_context}\n\nRICHIESTA: {user_input}"
        else:
            full_input = user_input

        # STEP 1: Ask LLM what to do
        self.logger.info(f"Calendar agent: analyzing request")
        response = await gemini.generate(
            full_input,
            system_instruction=prompt,
            model="gemini-2.5-flash",
            temperature=0.1
        )

        # Parse response
        try:
            decision = self._parse_json_response(response)
        except Exception as e:
            self.logger.error(f"Failed to parse LLM response: {response[:200]}")
            return {"error": f"Non ho capito la richiesta: {str(e)}"}

        # Handle list of operations (multiple create_event)
        if isinstance(decision, list):
            results = []
            for op in decision:
                tool_name = op.get("tool")
                params = op.get("params", {})
                self.logger.info(f"Calendar agent: {tool_name} with {params}")
                result = await self._execute_tool(tool_name, params)
                results.append(result)
            return {"multiple_results": results} if len(results) > 1 else results[0]

        tool_name = decision.get("tool")
        params = decision.get("params", {})
        self.logger.info(f"Calendar agent: {tool_name} with {params}")

        # If tool is none, return message
        if tool_name == "none":
            return {"message": decision.get("message", "Nessuna azione necessaria")}

        # STEP 1.5: If it's a search/get that might need follow-up, execute and check
        if tool_name in ("get_events", "search_events"):
            search_result = await self._execute_tool(tool_name, params)
            events = search_result.get("events", [])

            # Check if user just wanted to see events (not modify/delete)
            request_lower = user_input.lower()
            is_read_only = any(word in request_lower for word in [
                "agenda", "programma", "eventi", "appuntamenti", "cosa ho",
                "che ho", "mostra", "fammi vedere", "quali", "cosa c'è"
            ])
            wants_action = any(word in request_lower for word in [
                "cancella", "elimina", "rimuovi", "sposta", "modifica",
                "cambia", "aggiorna", "delete", "remove", "update"
            ])

            if is_read_only and not wants_action:
                # User just wanted to see events
                return search_result

            if not events:
                return search_result  # No events found, return as-is

            # STEP 2: We have events and user wants to do something - ask LLM to pick
            self.logger.info(f"Calendar agent: step 2 - choosing from {len(events)} events")

            events_formatted = self._format_events_for_llm(events)
            followup_prompt = FOLLOWUP_PROMPT.format(
                today=today,
                weekday=weekday,
                original_request=user_input,
                events_list=events_formatted,
                tools=tools_str
            )

            followup_response = await gemini.generate(
                f"Richiesta originale: {user_input}\n\nContesto: {conversation_context}" if conversation_context else user_input,
                system_instruction=followup_prompt,
                model="gemini-2.5-flash",
                temperature=0.1
            )

            try:
                followup_decision = self._parse_json_response(followup_response)
            except Exception as e:
                self.logger.error(f"Failed to parse followup response: {followup_response[:200]}")
                return search_result  # Return search results if we can't parse followup

            followup_tool = followup_decision.get("tool")
            followup_params = followup_decision.get("params", {})

            if followup_tool == "none":
                return search_result

            # Validate event_id exists
            if followup_tool in ("update_event", "delete_event"):
                event_id = followup_params.get("event_id")
                if not event_id or event_id == "FOUND_EVENT_ID":
                    self.logger.error(f"LLM returned invalid event_id: {event_id}")
                    return {"error": "Non sono riuscito a identificare l'evento corretto", "events": events}

                # Verify event_id is in our results
                valid_ids = [e.get("id") for e in events]
                if event_id not in valid_ids:
                    self.logger.warning(f"LLM returned event_id {event_id} not in results {valid_ids}")
                    # Still try to execute - maybe it's a valid ID from context

            self.logger.info(f"Calendar agent step 2: {followup_tool} with {followup_params}")
            return await self._execute_tool(followup_tool, followup_params)

        # Direct execution for create_event, etc.
        return await self._execute_tool(tool_name, params)

    def _parse_json_response(self, response: str) -> dict | list:
        """Parse JSON from LLM response, handling markdown code blocks."""
        clean = response.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
            clean = clean.strip()
        return json.loads(clean)

    async def _execute_tool(self, tool_name: str, params: dict) -> dict:
        """Execute the selected tool."""
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

            start = datetime.fromisoformat(f"{start_date}T00:00")
            end = datetime.fromisoformat(f"{end_date}T23:59")

            events = calendar_client.get_events(start=start, end=end)

            if events and user_id:
                asyncio.create_task(self._enrich_entities_from_events(user_id, events))

            return {
                "operation": "get_events",
                "period": f"{start_date} - {end_date}",
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

            start_date = params.get("start_date", now.strftime("%Y-%m-%d"))
            end_date = params.get("end_date", (now + timedelta(days=30)).strftime("%Y-%m-%d"))

            start = datetime.fromisoformat(f"{start_date}T00:00")
            end = datetime.fromisoformat(f"{end_date}T23:59")

            all_events = calendar_client.get_events(start=start, end=end, max_results=100)

            # Filter by query
            matching = []
            for event in all_events:
                title = (event.get("title") or "").lower()
                description = (event.get("description") or "").lower()
                if query in title or query in description:
                    matching.append(event)

            if matching and user_id:
                asyncio.create_task(self._enrich_entities_from_events(user_id, matching))

            return {
                "operation": "search_events",
                "query": query,
                "events": matching,
                "count": len(matching),
                "message": f"Trovati {len(matching)} eventi" if matching else f"Nessun evento trovato con '{query}'"
            }
        except Exception as e:
            self.logger.error(f"search_events failed: {e}")
            return {"error": f"Errore nella ricerca: {str(e)}"}

    async def _tool_create_event(self, params: dict) -> dict:
        """Create a calendar event."""
        try:
            start_date = params.get("start_date") or params.get("date")
            end_date = params.get("end_date") or start_date
            start_time = params.get("start_time")
            end_time = params.get("end_time")
            title = params.get("title", "Evento")

            start = datetime.fromisoformat(f"{start_date}T{start_time}")
            end = datetime.fromisoformat(f"{end_date}T{end_time}")

            attendees_raw = params.get("attendees", "")
            attendees = None
            if attendees_raw:
                attendees = [e.strip() for e in attendees_raw.split(",") if e.strip() and "@" in e]

            add_meet_param = params.get("add_meet")
            if isinstance(add_meet_param, str):
                add_meet = add_meet_param.lower() == "true"
            elif isinstance(add_meet_param, bool):
                add_meet = add_meet_param
            else:
                add_meet = bool(attendees)

            event = calendar_client.create_event(
                title=title,
                start=start,
                end=end,
                description=params.get("description"),
                location=params.get("location"),
                attendees=attendees,
                add_meet=add_meet
            )

            if start_date == end_date:
                message = f"Evento '{event['title']}' creato per {start_date} {start_time}-{end_time}"
            else:
                message = f"Evento '{event['title']}' creato da {start_date} {start_time} a {end_date} {end_time}"

            if attendees:
                message += f" con {len(attendees)} partecipanti"
            if event.get("meet_link"):
                message += f"\n📹 Meet: {event['meet_link']}"

            return {
                "operation": "create_event",
                "event": event,
                "message": message
            }
        except Exception as e:
            self.logger.error(f"create_event failed: {e}")
            return {"error": f"Errore nella creazione: {str(e)}"}

    async def _tool_update_event(self, params: dict) -> dict:
        """Update an existing calendar event."""
        try:
            event_id = params.get("event_id")
            if not event_id:
                return {"error": "event_id mancante"}

            updates = {}

            if params.get("title"):
                updates["title"] = params["title"]
            if params.get("description"):
                updates["description"] = params["description"]
            if params.get("location"):
                updates["location"] = params["location"]

            start_date = params.get("start_date") or params.get("date")
            end_date = params.get("end_date") or start_date
            start_time = params.get("start_time")
            end_time = params.get("end_time")

            if start_date and start_time:
                updates["start"] = datetime.fromisoformat(f"{start_date}T{start_time}")
            elif start_time:
                updates["start"] = datetime.fromisoformat(f"{datetime.now().strftime('%Y-%m-%d')}T{start_time}")

            if end_date and end_time:
                updates["end"] = datetime.fromisoformat(f"{end_date}T{end_time}")
            elif end_time:
                use_date = end_date or start_date or datetime.now().strftime('%Y-%m-%d')
                updates["end"] = datetime.fromisoformat(f"{use_date}T{end_time}")

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
            return {"error": f"Errore nell'aggiornamento: {str(e)}"}

    async def _tool_delete_event(self, params: dict) -> dict:
        """Delete a calendar event."""
        try:
            event_id = params.get("event_id")
            if not event_id:
                return {"error": "event_id mancante"}

            calendar_client.delete_event(event_id)

            return {
                "operation": "delete_event",
                "event_id": event_id,
                "message": "Evento eliminato"
            }
        except Exception as e:
            self.logger.error(f"delete_event failed: {e}")
            return {"error": f"Errore nell'eliminazione: {str(e)}"}

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
