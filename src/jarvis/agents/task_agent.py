"""Task agent - LLM-powered CRUD for Notion tasks."""

from datetime import datetime, timedelta
from typing import Any
import json

from jarvis.agents.base import BaseAgent
from jarvis.core.state import JarvisState
from jarvis.config import get_settings
from jarvis.integrations.notion import notion_client, NotionClient
from jarvis.integrations.gemini import gemini
from jarvis.utils.logging import get_logger

logger = get_logger(__name__)

TASK_TOOLS = [
    {
        "name": "list_databases",
        "description": "Elenca i database Notion disponibili.",
        "parameters": {},
    },
    {
        "name": "query_tasks",
        "description": "Cerca task in un database con filtri opzionali. Per default esclude le task completate/done.",
        "parameters": {
            "database_id": "ID del database Notion",
            "status": "Filtra per stato (opzionale)",
            "due_before": "Scadenza prima di YYYY-MM-DD (opzionale)",
            "due_after": "Scadenza dopo YYYY-MM-DD (opzionale)",
            "text": "Filtra per testo nel titolo (opzionale)",
            "assignee": "Nome dell'assegnatario per filtrare (opzionale, default: utente corrente)",
            "all_assignees": "true per vedere task di TUTTI, non solo le proprie (opzionale)",
            "include_done": "true per includere anche task completate (opzionale, default: false)",
        },
    },
    {
        "name": "create_task",
        "description": "Crea una nuova task nel database.",
        "parameters": {
            "database_id": "ID del database Notion",
            "title": "Titolo della task (obbligatorio)",
            "status": "Stato iniziale (opzionale, default quello di default del DB)",
            "due_date": "Scadenza in formato YYYY-MM-DD (opzionale)",
            "priority": "Priorita (opzionale)",
            "tags": "Tag separati da virgola (opzionale)",
            "notes": "Note aggiuntive (opzionale)",
        },
    },
    {
        "name": "update_task",
        "description": "Aggiorna una task esistente.",
        "parameters": {
            "page_id": "ID della pagina Notion (obbligatorio)",
            "title": "Nuovo titolo (opzionale)",
            "status": "Nuovo stato (opzionale)",
            "due_date": "Nuova scadenza YYYY-MM-DD (opzionale)",
            "priority": "Nuova priorita (opzionale)",
            "notes": "Nuove note (opzionale)",
        },
    },
    {
        "name": "complete_task",
        "description": "Segna una task come completata. Puoi specificare page_id o title_search.",
        "parameters": {
            "page_id": "ID della pagina (opzionale se usi title_search)",
            "title_search": "Cerca task per titolo e completa (opzionale se usi page_id)",
            "database_id": "ID del database (richiesto con title_search)",
        },
    },
    {
        "name": "search_tasks",
        "description": "Ricerca full-text in tutti i database Notion.",
        "parameters": {
            "query": "Testo da cercare",
        },
    },
]

AGENT_SYSTEM_PROMPT = """Sei un agente per la gestione task su Notion. L'utente e {user_name}.

OGGI: {today} ({weekday})

DATABASE DISPONIBILI:
{databases_info}

TOOL DISPONIBILI:
{tools}

REGOLE:
1. Se l'utente chiede di vedere/elencare task, usa query_tasks con il database corretto
2. Se c'e un solo database, usalo sempre senza chiedere
3. Se ci sono piu database, scegli quello piu appropriato dal contesto (es. "task di lavoro" → database Lavoro)
4. Per completare una task per nome, usa complete_task con title_search
5. Per creare task, inferisci il database dal contesto
6. Usa le proprieta disponibili nel database (status, priority, date, ecc.)
7. Se una proprieta non esiste nel database, ignorala silenziosamente
8. "le mie task", "mostra task", senza specificare chi → filtra SOLO le task assegnate a {user_name}
9. Se l'utente chiede task di qualcun altro o di tutti, NON filtrare per assegnatario

FORMATO OUTPUT: Solo JSON valido
- Singola operazione: {{"tool": "nome", "params": {{...}}}}
- Se non serve alcuna azione: {{"tool": "none", "message": "spiegazione"}}

ESEMPI:
- "mostra le mie task" → {{"tool": "query_tasks", "params": {{"database_id": "DB_ID"}}}}
- "task in scadenza" → {{"tool": "query_tasks", "params": {{"database_id": "DB_ID", "due_before": "{in_7_days}"}}}}
- "crea task comprare latte" → {{"tool": "create_task", "params": {{"database_id": "DB_ID", "title": "Comprare latte"}}}}
- "completa la task report" → {{"tool": "complete_task", "params": {{"title_search": "report", "database_id": "DB_ID"}}}}
- "cerca budget" → {{"tool": "search_tasks", "params": {{"query": "budget"}}}}

Rispondi SOLO con JSON."""


class TaskAgent(BaseAgent):
    name = "task"
    resource_type = None  # No caching

    async def _get_databases_info(self) -> tuple[list[dict], str]:
        """Load databases with schemas and build info string for LLM."""
        all_databases = await notion_client.discover_databases()
        if not all_databases:
            return [], "Nessun database trovato."

        # Filter to configured task databases only
        settings = get_settings()
        allowed_ids = settings.notion_task_database_ids
        if allowed_ids:
            # Normalize IDs (Notion sometimes uses/omits dashes)
            allowed_normalized = {aid.replace("-", "") for aid in allowed_ids}
            databases = [
                db for db in all_databases
                if db["id"] in allowed_ids or db["id"].replace("-", "") in allowed_normalized
            ]
            logger.info(f"Task DB filter: {len(all_databases)} total → {len(databases)} allowed (config: {len(allowed_ids)} IDs)")
        else:
            databases = all_databases
            logger.warning("No NOTION_TASK_DATABASES configured, using ALL databases")

        if not databases:
            return [], "Nessun database task configurato."

        info_parts = []
        for db in databases:
            schema = await notion_client.get_database_schema(db["id"])
            props = schema.get("properties", {})

            prop_descriptions = []
            for pname, pinfo in props.items():
                desc = f"  - {pname} ({pinfo['type']})"
                if pinfo.get("options"):
                    desc += f" → opzioni: {', '.join(pinfo['options'][:10])}"
                prop_descriptions.append(desc)

            info_parts.append(
                f"- **{db['title']}** (id: {db['id']})\n"
                + "\n".join(prop_descriptions)
            )

        return databases, "\n\n".join(info_parts)

    def _find_property_by_role(self, schema: dict, role: str) -> tuple[str, str] | None:
        """Find a property in schema by its semantic role.

        Returns (property_name, property_type) or None.
        """
        props = schema.get("properties", {})

        if role == "title":
            for name, info in props.items():
                if info["type"] == "title":
                    return (name, "title")

        elif role == "status":
            for name, info in props.items():
                if info["type"] == "status":
                    return (name, "status")
            for name, info in props.items():
                if info["type"] == "select" and any(
                    kw in name.lower() for kw in ["stato", "status", "state"]
                ):
                    return (name, "select")

        elif role == "date":
            for name, info in props.items():
                if info["type"] == "date" and any(
                    kw in name.lower()
                    for kw in ["scadenza", "due", "data", "deadline", "date"]
                ):
                    return (name, "date")
            # Fallback: first date property
            for name, info in props.items():
                if info["type"] == "date":
                    return (name, "date")

        elif role == "priority":
            for name, info in props.items():
                if info["type"] in ("select", "multi_select") and any(
                    kw in name.lower() for kw in ["priorit", "priority"]
                ):
                    return (name, info["type"])

        elif role == "tags":
            for name, info in props.items():
                if info["type"] == "multi_select" and any(
                    kw in name.lower() for kw in ["tag", "label", "categor", "etichett"]
                ):
                    return (name, "multi_select")

        elif role == "notes":
            for name, info in props.items():
                if info["type"] == "rich_text" and any(
                    kw in name.lower() for kw in ["note", "descri", "dettagl", "comment"]
                ):
                    return (name, "rich_text")

        return None

    def _find_done_status(self, schema: dict) -> str | None:
        """Find the 'done/completed' status value in a database schema."""
        props = schema.get("properties", {})
        for name, info in props.items():
            if info["type"] == "status":
                for opt in info.get("options", []):
                    if opt.lower() in ("done", "completato", "completata", "fatto", "fatta", "completed", "chiuso", "chiusa"):
                        return opt
                # Check groups for "Complete" group
                for group in info.get("groups", []):
                    if group["name"].lower() in ("complete", "completato", "done"):
                        # Return first option in the complete group
                        for opt in info.get("options", []):
                            if opt.lower() in ("done", "completato", "completata", "fatto", "completed"):
                                return opt
            elif info["type"] == "select" and any(
                kw in name.lower() for kw in ["stato", "status"]
            ):
                for opt in info.get("options", []):
                    if opt.lower() in ("done", "completato", "completata", "fatto", "completed"):
                        return opt
        return "Done"  # Default fallback

    async def _execute(self, state: JarvisState) -> Any:
        """Execute task operations with LLM tool dispatch."""
        user_input = state.get("enriched_input", state["current_input"])
        user_id = state["user_id"]
        self._current_user_id = user_id

        # Date info
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        in_7_days = (now + timedelta(days=7)).strftime("%Y-%m-%d")
        weekday_names = ["Lunedi", "Martedi", "Mercoledi", "Giovedi", "Venerdi", "Sabato", "Domenica"]
        weekday = weekday_names[now.weekday()]

        # Load databases and schemas
        databases, databases_info = await self._get_databases_info()
        if not databases:
            return {"error": "Nessun database Notion trovato. Verifica la configurazione dell'integrazione."}

        settings = get_settings()
        user_name = settings.notion_user_name or "utente"

        tools_str = json.dumps(TASK_TOOLS, indent=2, ensure_ascii=False)

        prompt = AGENT_SYSTEM_PROMPT.format(
            today=today,
            weekday=weekday,
            databases_info=databases_info,
            tools=tools_str,
            in_7_days=in_7_days,
            user_name=user_name,
        )

        # Set user context for LLM logging
        gemini.set_user_context(user_id)

        # Ask LLM what to do
        self.logger.info("Task agent: analyzing request")
        response = await gemini.generate(
            user_input,
            system_instruction=prompt,
            model="gemini-2.5-flash",
            temperature=0.1,
        )

        # Parse response
        try:
            decision = self._parse_json_response(response)
        except Exception as e:
            self.logger.error(f"Failed to parse LLM response: {response[:200]}")
            return {"error": f"Non ho capito la richiesta: {e}"}

        tool_name = decision.get("tool")
        params = decision.get("params", {})
        self.logger.info(f"Task agent: {tool_name} with {params}")

        if tool_name == "none":
            return {"message": decision.get("message", "Nessuna azione necessaria")}

        return await self._execute_tool(tool_name, params)

    def _parse_json_response(self, response: str) -> dict:
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
        if tool_name == "list_databases":
            return await self._tool_list_databases()
        elif tool_name == "query_tasks":
            return await self._tool_query_tasks(params)
        elif tool_name == "create_task":
            return await self._tool_create_task(params)
        elif tool_name == "update_task":
            return await self._tool_update_task(params)
        elif tool_name == "complete_task":
            return await self._tool_complete_task(params)
        elif tool_name == "search_tasks":
            return await self._tool_search_tasks(params)
        else:
            return {"error": f"Tool sconosciuto: {tool_name}"}

    def _summarize_tasks(self, tasks: list[dict], schema: dict) -> list[dict]:
        """Distill raw Notion page data into compact task summaries."""
        title_prop = self._find_property_by_role(schema, "title")
        status_prop = self._find_property_by_role(schema, "status")
        date_prop = self._find_property_by_role(schema, "date")
        priority_prop = self._find_property_by_role(schema, "priority")

        summaries = []
        for t in tasks:
            summary = {"id": t.get("id", "")}
            if title_prop:
                summary["title"] = t.get(title_prop[0], "Senza titolo")
            if status_prop:
                summary["status"] = t.get(status_prop[0])
            if date_prop:
                raw = t.get(date_prop[0])
                if isinstance(raw, dict):
                    summary["due"] = raw.get("start")
                elif raw:
                    summary["due"] = str(raw)
            if priority_prop:
                summary["priority"] = t.get(priority_prop[0])

            # Include assignee if present (people property)
            props = schema.get("properties", {})
            for name, info in props.items():
                if info["type"] == "people" and t.get(name):
                    summary["assignee"] = t[name]
                    break

            summaries.append(summary)
        return summaries

    def _build_text_digest(self, summaries: list[dict], db_title: str = "") -> str:
        """Build a pre-formatted text digest of tasks for the LLM.

        Instead of dumping raw JSON, produce a structured summary that
        the orchestrator LLM can relay almost verbatim.
        """
        if not summaries:
            return "Nessuna task trovata."

        total = len(summaries)

        # Group by status
        by_status: dict[str, list[dict]] = {}
        for s in summaries:
            status = s.get("status") or "Senza stato"
            by_status.setdefault(status, []).append(s)

        # Group by priority
        by_priority: dict[str, int] = {}
        for s in summaries:
            prio = s.get("priority") or "Senza priorita"
            by_priority[prio] = by_priority.get(prio, 0) + 1

        lines = []
        if db_title:
            lines.append(f"Database: {db_title}")
        lines.append(f"Totale: {total} task attive")
        lines.append("")

        # Status breakdown
        lines.append("Per stato:")
        for status, tasks in by_status.items():
            lines.append(f"  - {status}: {len(tasks)}")

        # Priority breakdown if available
        if any(s.get("priority") for s in summaries):
            lines.append("")
            lines.append("Per priorita:")
            for prio, count in sorted(by_priority.items()):
                lines.append(f"  - {prio}: {count}")

        # List ALL tasks grouped by status
        lines.append("")
        for status, tasks in by_status.items():
            lines.append(f"\n--- {status} ({len(tasks)}) ---")
            for t in tasks:
                parts = [t.get("title", "?")]
                if t.get("due"):
                    parts.append(f"scad: {t['due']}")
                if t.get("assignee"):
                    assignee = t["assignee"]
                    if isinstance(assignee, list):
                        assignee = ", ".join(str(a) for a in assignee)
                    parts.append(f"→ {assignee}")
                if t.get("priority"):
                    parts.append(f"[{t['priority']}]")
                lines.append(f"  - {' | '.join(parts)}")

        return "\n".join(lines)

    async def _tool_list_databases(self) -> dict:
        """List available Notion databases."""
        try:
            databases = await notion_client.discover_databases()
            return {
                "operation": "list_databases",
                "databases": databases,
                "count": len(databases),
            }
        except Exception as e:
            self.logger.error(f"list_databases failed: {e}")
            return {"error": f"Errore nel recupero database: {e}"}

    async def _tool_query_tasks(self, params: dict) -> dict:
        """Query tasks with filters."""
        try:
            db_id = params.get("database_id")
            if not db_id:
                return {"error": "database_id mancante"}

            schema = await notion_client.get_database_schema(db_id)

            # Build Notion filter
            filters = []

            # Status filter
            status_value = params.get("status")
            if status_value:
                status_prop = self._find_property_by_role(schema, "status")
                if status_prop:
                    pname, ptype = status_prop
                    filters.append({
                        "property": pname,
                        ptype: {"equals": status_value},
                    })

            # Date filters
            date_prop = self._find_property_by_role(schema, "date")
            if date_prop:
                pname, _ = date_prop
                if params.get("due_before"):
                    filters.append({
                        "property": pname,
                        "date": {"on_or_before": params["due_before"]},
                    })
                if params.get("due_after"):
                    filters.append({
                        "property": pname,
                        "date": {"on_or_after": params["due_after"]},
                    })

            # Build final filter
            filter_obj = None
            if len(filters) == 1:
                filter_obj = filters[0]
            elif len(filters) > 1:
                filter_obj = {"and": filters}

            # Sort by date if available
            sorts = None
            if date_prop:
                sorts = [{"property": date_prop[0], "direction": "ascending"}]

            tasks = await notion_client.query_database(db_id, filter_obj, sorts)

            # Exclude completed/done/archived tasks by default
            exclude_done = params.get("include_done") is None
            if exclude_done:
                status_prop = self._find_property_by_role(schema, "status")
                if status_prop:
                    done_keywords = {"done", "completato", "completata", "fatto", "fatta", "completed", "chiuso", "chiusa", "archiviato"}
                    sname = status_prop[0]
                    tasks = [
                        t for t in tasks
                        if str(t.get(sname, "")).lower() not in done_keywords
                    ]

            # Client-side text filter if needed
            text_filter = params.get("text", "").lower()
            if text_filter:
                title_prop = self._find_property_by_role(schema, "title")
                if title_prop:
                    title_name = title_prop[0]
                    tasks = [
                        t for t in tasks
                        if text_filter in str(t.get(title_name, "")).lower()
                    ]

            # Client-side assignee filter
            all_assignees = params.get("all_assignees")
            if isinstance(all_assignees, str):
                all_assignees = all_assignees.lower() == "true"

            if not all_assignees:
                assignee_filter = params.get("assignee", "").strip()
                if not assignee_filter:
                    settings = get_settings()
                    assignee_filter = settings.notion_user_name

                if assignee_filter:
                    assignee_lower = assignee_filter.lower()
                    # Find people property in schema
                    people_prop_name = None
                    props = schema.get("properties", {})
                    for name, info in props.items():
                        if info["type"] == "people":
                            people_prop_name = name
                            break

                    if people_prop_name:
                        tasks = [
                            t for t in tasks
                            if not t.get(people_prop_name)  # unassigned → include
                            or any(
                                assignee_lower in str(p).lower()
                                for p in t.get(people_prop_name, [])
                            )
                        ]

            summaries = self._summarize_tasks(tasks, schema)

            # Find database title for the digest
            db_title = ""
            all_databases = await notion_client.discover_databases()
            for db in all_databases:
                if db["id"] == db_id:
                    db_title = db.get("title", "")
                    break

            digest = self._build_text_digest(summaries, db_title)
            return {
                "operation": "query_tasks",
                "digest": digest,
                "count": len(summaries),
            }
        except Exception as e:
            self.logger.error(f"query_tasks failed: {e}")
            return {"error": f"Errore nella query: {e}"}

    async def _tool_create_task(self, params: dict) -> dict:
        """Create a new task."""
        try:
            db_id = params.get("database_id")
            title = params.get("title")
            if not db_id or not title:
                return {"error": "database_id e title sono obbligatori"}

            schema = await notion_client.get_database_schema(db_id)
            properties = {}

            # Title (required)
            title_prop = self._find_property_by_role(schema, "title")
            if title_prop:
                properties[title_prop[0]] = NotionClient.build_property_value("title", title)

            # Status
            if params.get("status"):
                status_prop = self._find_property_by_role(schema, "status")
                if status_prop:
                    properties[status_prop[0]] = NotionClient.build_property_value(
                        status_prop[1], params["status"]
                    )

            # Due date
            if params.get("due_date"):
                date_prop = self._find_property_by_role(schema, "date")
                if date_prop:
                    properties[date_prop[0]] = NotionClient.build_property_value(
                        "date", params["due_date"]
                    )

            # Priority
            if params.get("priority"):
                prio_prop = self._find_property_by_role(schema, "priority")
                if prio_prop:
                    properties[prio_prop[0]] = NotionClient.build_property_value(
                        prio_prop[1], params["priority"]
                    )

            # Tags
            if params.get("tags"):
                tags_prop = self._find_property_by_role(schema, "tags")
                if tags_prop:
                    properties[tags_prop[0]] = NotionClient.build_property_value(
                        "multi_select", params["tags"]
                    )

            # Notes
            if params.get("notes"):
                notes_prop = self._find_property_by_role(schema, "notes")
                if notes_prop:
                    properties[notes_prop[0]] = NotionClient.build_property_value(
                        "rich_text", params["notes"]
                    )

            result = await notion_client.create_page(db_id, properties)
            return {
                "operation": "create_task",
                "task": result,
                "message": f"Task '{title}' creata",
            }
        except Exception as e:
            self.logger.error(f"create_task failed: {e}")
            return {"error": f"Errore nella creazione: {e}"}

    async def _get_schema_for_db(self, db_id: str = None) -> dict | None:
        """Get schema for a specific DB or the first available one."""
        if db_id:
            return await notion_client.get_database_schema(db_id)
        databases = await notion_client.discover_databases()
        if databases:
            return await notion_client.get_database_schema(databases[0]["id"])
        return None

    async def _tool_update_task(self, params: dict) -> dict:
        """Update an existing task."""
        try:
            page_id = params.get("page_id")
            if not page_id:
                return {"error": "page_id mancante"}

            # Use database_id if provided, otherwise fallback to first DB
            schema = await self._get_schema_for_db(params.get("database_id"))

            if not schema:
                return {"error": "Nessun database trovato per il mapping delle proprieta"}

            properties = {}

            if params.get("title"):
                title_prop = self._find_property_by_role(schema, "title")
                if title_prop:
                    properties[title_prop[0]] = NotionClient.build_property_value("title", params["title"])

            if params.get("status"):
                status_prop = self._find_property_by_role(schema, "status")
                if status_prop:
                    properties[status_prop[0]] = NotionClient.build_property_value(
                        status_prop[1], params["status"]
                    )

            if params.get("due_date"):
                date_prop = self._find_property_by_role(schema, "date")
                if date_prop:
                    properties[date_prop[0]] = NotionClient.build_property_value("date", params["due_date"])

            if params.get("priority"):
                prio_prop = self._find_property_by_role(schema, "priority")
                if prio_prop:
                    properties[prio_prop[0]] = NotionClient.build_property_value(
                        prio_prop[1], params["priority"]
                    )

            if params.get("notes"):
                notes_prop = self._find_property_by_role(schema, "notes")
                if notes_prop:
                    properties[notes_prop[0]] = NotionClient.build_property_value("rich_text", params["notes"])

            if not properties:
                return {"error": "Nessuna modifica specificata"}

            result = await notion_client.update_page(page_id, properties)
            return {
                "operation": "update_task",
                "task": result,
                "message": "Task aggiornata",
            }
        except Exception as e:
            self.logger.error(f"update_task failed: {e}")
            return {"error": f"Errore nell'aggiornamento: {e}"}

    async def _tool_complete_task(self, params: dict) -> dict:
        """Mark a task as completed. Supports page_id or title_search."""
        try:
            page_id = params.get("page_id")
            title_search = params.get("title_search")
            db_id = params.get("database_id")
            schema = None

            if not page_id and not title_search:
                return {"error": "Serve page_id o title_search"}

            # Two-step: search first if using title_search
            if title_search and not page_id:
                if not db_id:
                    # Use first database
                    databases = await notion_client.discover_databases()
                    if databases:
                        db_id = databases[0]["id"]
                    else:
                        return {"error": "Nessun database trovato"}

                schema = await notion_client.get_database_schema(db_id)
                tasks = await notion_client.query_database(db_id)

                # Find matching task by title
                title_prop = self._find_property_by_role(schema, "title")
                if not title_prop:
                    return {"error": "Proprieta title non trovata nel database"}

                title_name = title_prop[0]
                search_lower = title_search.lower()
                matches = [
                    t for t in tasks
                    if search_lower in str(t.get(title_name, "")).lower()
                ]

                if not matches:
                    return {
                        "error": f"Nessuna task trovata con '{title_search}'",
                        "tasks_available": [
                            {title_name: t.get(title_name), "id": t["id"]}
                            for t in tasks[:10]
                        ],
                    }

                if len(matches) > 1:
                    return {
                        "message": f"Trovate {len(matches)} task corrispondenti. Quale intendi?",
                        "matches": [
                            {title_name: m.get(title_name), "id": m["id"]}
                            for m in matches
                        ],
                    }

                page_id = matches[0]["id"]

            # Reuse schema if already fetched from title_search path, otherwise fetch
            if not schema:
                schema = await self._get_schema_for_db(db_id)

            if not schema:
                return {"error": "Nessuno schema trovato"}

            done_value = self._find_done_status(schema)
            status_prop = self._find_property_by_role(schema, "status")

            if not status_prop:
                return {"error": "Proprieta status non trovata nel database"}

            properties = {
                status_prop[0]: NotionClient.build_property_value(status_prop[1], done_value)
            }

            result = await notion_client.update_page(page_id, properties)
            return {
                "operation": "complete_task",
                "task": result,
                "message": f"Task completata (stato: {done_value})",
            }
        except Exception as e:
            self.logger.error(f"complete_task failed: {e}")
            return {"error": f"Errore nel completamento: {e}"}

    async def _tool_search_tasks(self, params: dict) -> dict:
        """Full-text search across all databases."""
        try:
            query = params.get("query", "")
            if not query:
                return {"error": "query mancante"}

            results = await notion_client.search_pages(query)
            return {
                "operation": "search_tasks",
                "query": query,
                "tasks": results,
                "count": len(results),
            }
        except Exception as e:
            self.logger.error(f"search_tasks failed: {e}")
            return {"error": f"Errore nella ricerca: {e}"}


# Singleton
task_agent = TaskAgent()
