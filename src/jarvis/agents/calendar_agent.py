"""Calendar agent - LLM-powered with tool calling."""

from datetime import datetime, timedelta
from typing import Any
import json
import asyncio
from jarvis.agents.base import BaseAgent
from jarvis.core.state import JarvisState
from jarvis.integrations.google_calendar import calendar_client
from jarvis.integrations.gemini import gemini

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
        "name": "create_event",
        "description": "Crea un nuovo evento nel calendario",
        "parameters": {
            "title": "Titolo dell'evento",
            "date": "Data in formato YYYY-MM-DD",
            "start_time": "Ora inizio in formato HH:MM",
            "end_time": "Ora fine in formato HH:MM",
            "description": "Descrizione opzionale",
            "location": "Luogo opzionale"
        }
    },
    {
        "name": "delete_event",
        "description": "Elimina un evento dal calendario",
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

AGENT_SYSTEM_PROMPT = """Sei un agente calendario. Il tuo compito è capire la richiesta dell'utente e chiamare i tool appropriati.

OGGI: {today}
GIORNO DELLA SETTIMANA: {weekday}

TOOL DISPONIBILI:
{tools}

REGOLE:
1. Analizza la richiesta e decidi quali tool usare
2. Calcola le date corrette (es: "domani" = {tomorrow}, "lunedì prossimo" = calcola)
3. Se la richiesta contiene MULTIPLE OPERAZIONI (es: "crea due eventi", "fissa un appuntamento alle 10 e uno alle 14"), restituisci una LISTA di tool calls
4. Rispondi SOLO con un JSON valido. Formato:
   - Singola operazione: {{"tool": "nome_tool", "params": {{...}}}}
   - Multiple operazioni: [{{"tool": "nome_tool", "params": {{...}}}}, {{"tool": "nome_tool", "params": {{...}}}}]

ESEMPI:
- "cosa ho domani mattina" → {{"tool": "get_events", "params": {{"start_date": "{tomorrow}", "end_date": "{tomorrow}", "start_time": "00:00", "end_time": "13:00"}}}}
- "bloccami giovedì 15-17" → {{"tool": "create_event", "params": {{"title": "Occupato", "date": "YYYY-MM-DD del giovedì", "start_time": "15:00", "end_time": "17:00"}}}}
- "fissami un appuntamento alle 10 con Mario e uno alle 14 con Luigi" → [{{"tool": "create_event", "params": {{"title": "Appuntamento con Mario", "date": "{today}", "start_time": "10:00", "end_time": "11:00"}}}}, {{"tool": "create_event", "params": {{"title": "Appuntamento con Luigi", "date": "{today}", "start_time": "14:00", "end_time": "15:00"}}}}]

Rispondi SOLO con il JSON, nient'altro."""


class CalendarAgent(BaseAgent):
    name = "calendar"
    resource_type = "calendar"

    async def _execute(self, state: JarvisState) -> Any:
        """Execute calendar operations using LLM reasoning."""
        user_input = state["current_input"]

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

        # Ask LLM what to do
        response = await gemini.generate(
            user_input,
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
                # Multiple tool calls - execute in parallel
                self.logger.info(f"Calendar agent: {len(decision)} tool calls to execute")
                tasks = []
                for call in decision:
                    tool_name = call.get("tool")
                    params = call.get("params", {})
                    self.logger.info(f"Calendar agent decision: {tool_name} with {params}")
                    tasks.append(self._execute_tool(tool_name, params))

                results = await asyncio.gather(*tasks, return_exceptions=True)
                # Convert exceptions to error dicts
                processed_results = []
                for r in results:
                    if isinstance(r, Exception):
                        processed_results.append({"error": str(r)})
                    else:
                        processed_results.append(r)
                return {"multiple_results": processed_results}
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

        if tool_name == "get_events":
            return await self._tool_get_events(params)
        elif tool_name == "create_event":
            return await self._tool_create_event(params)
        elif tool_name == "delete_event":
            return await self._tool_delete_event(params)
        elif tool_name == "find_free_slots":
            return await self._tool_find_free_slots(params)
        else:
            return {"error": f"Tool sconosciuto: {tool_name}"}

    async def _tool_get_events(self, params: dict) -> dict:
        """Get calendar events."""
        try:
            start_date = params.get("start_date")
            end_date = params.get("end_date")
            start_time = params.get("start_time", "00:00")
            end_time = params.get("end_time", "23:59")

            start = datetime.fromisoformat(f"{start_date}T{start_time}")
            end = datetime.fromisoformat(f"{end_date}T{end_time}")

            events = calendar_client.get_events(start=start, end=end)

            return {
                "operation": "get_events",
                "period": f"{start_date} {start_time} - {end_date} {end_time}",
                "events": events,
                "count": len(events)
            }
        except Exception as e:
            self.logger.error(f"get_events failed: {e}")
            return {"error": f"Errore nel recupero eventi: {str(e)}"}

    async def _tool_create_event(self, params: dict) -> dict:
        """Create a calendar event."""
        try:
            date = params.get("date")
            start_time = params.get("start_time")
            end_time = params.get("end_time")

            start = datetime.fromisoformat(f"{date}T{start_time}")
            end = datetime.fromisoformat(f"{date}T{end_time}")

            event = calendar_client.create_event(
                title=params.get("title", "Nuovo evento"),
                start=start,
                end=end,
                description=params.get("description"),
                location=params.get("location")
            )

            return {
                "operation": "create_event",
                "event": event,
                "message": f"Evento '{event['title']}' creato per {date} {start_time}-{end_time}"
            }
        except Exception as e:
            self.logger.error(f"create_event failed: {e}")
            return {"error": f"Errore nella creazione evento: {str(e)}"}

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
