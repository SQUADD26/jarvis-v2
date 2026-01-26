"""Email agent - LLM-powered with tool calling."""

from typing import Any
import json
import asyncio
from jarvis.agents.base import BaseAgent
from jarvis.core.state import JarvisState
from jarvis.integrations.gmail import gmail_client
from jarvis.integrations.gemini import gemini

# Tool definitions for the LLM
EMAIL_TOOLS = [
    {
        "name": "get_inbox",
        "description": "Recupera le email dalla inbox",
        "parameters": {
            "max_results": "Numero massimo di email da recuperare (default: 10)",
            "unread_only": "Se true, solo email non lette (default: false)",
            "query": "Query di ricerca Gmail opzionale (es: 'from:mario@example.com')"
        }
    },
    {
        "name": "get_email",
        "description": "Legge il contenuto completo di una specifica email",
        "parameters": {
            "message_id": "ID dell'email da leggere"
        }
    },
    {
        "name": "send_email",
        "description": "Invia una nuova email",
        "parameters": {
            "to": "Indirizzo email destinatario",
            "subject": "Oggetto dell'email",
            "body": "Contenuto dell'email"
        }
    },
    {
        "name": "reply_email",
        "description": "Rispondi a una email esistente",
        "parameters": {
            "message_id": "ID dell'email a cui rispondere",
            "body": "Contenuto della risposta"
        }
    },
    {
        "name": "create_draft",
        "description": "Crea una bozza di email (senza inviarla)",
        "parameters": {
            "to": "Indirizzo email destinatario (opzionale per bozze)",
            "subject": "Oggetto dell'email",
            "body": "Contenuto dell'email"
        }
    },
    {
        "name": "search_emails",
        "description": "Cerca email con query Gmail",
        "parameters": {
            "query": "Query di ricerca (es: 'from:mario subject:progetto')",
            "max_results": "Numero massimo di risultati (default: 10)"
        }
    }
]

AGENT_SYSTEM_PROMPT = """Sei un agente email. Il tuo compito è capire la richiesta dell'utente e chiamare i tool appropriati.

TOOL DISPONIBILI:
{tools}

REGOLE:
1. Analizza la richiesta e decidi quali tool usare
2. Per "controllare email" o "nuove email" usa get_inbox con unread_only=true
3. Per "scrivere email" o "inviare a X" usa send_email
4. Per "bozza" o "draft" usa create_draft
5. Se l'utente vuole scrivere ma non specifica destinatario, usa create_draft
6. Se la richiesta contiene MULTIPLE OPERAZIONI (es: "invia due email", "scrivi a Mario e a Luigi"), restituisci una LISTA di tool calls
7. Rispondi SOLO con un JSON valido. Formato:
   - Singola operazione: {{"tool": "nome_tool", "params": {{...}}}}
   - Multiple operazioni: [{{"tool": "nome_tool", "params": {{...}}}}, {{"tool": "nome_tool", "params": {{...}}}}]

ESEMPI:
- "controlla le email" → {{"tool": "get_inbox", "params": {{"max_results": 10, "unread_only": false}}}}
- "ho email nuove?" → {{"tool": "get_inbox", "params": {{"max_results": 10, "unread_only": true}}}}
- "email da mario" → {{"tool": "search_emails", "params": {{"query": "from:mario", "max_results": 10}}}}
- "scrivi a test@example.com oggetto Ciao corpo Saluti" → {{"tool": "send_email", "params": {{"to": "test@example.com", "subject": "Ciao", "body": "Saluti"}}}}
- "invia un'email a mario@test.com e una a luigi@test.com" → [{{"tool": "send_email", "params": {{"to": "mario@test.com", "subject": "...", "body": "..."}}}}, {{"tool": "send_email", "params": {{"to": "luigi@test.com", "subject": "...", "body": "..."}}}}]

Rispondi SOLO con il JSON, nient'altro."""


class EmailAgent(BaseAgent):
    name = "email"
    resource_type = "email"

    async def _execute(self, state: JarvisState) -> Any:
        """Execute email operations using LLM reasoning."""
        user_input = state["current_input"]

        # Format tools for prompt
        tools_str = json.dumps(EMAIL_TOOLS, indent=2, ensure_ascii=False)

        # Build prompt
        prompt = AGENT_SYSTEM_PROMPT.format(tools=tools_str)

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
                self.logger.info(f"Email agent: {len(decision)} tool calls to execute")
                tasks = []
                for call in decision:
                    tool_name = call.get("tool")
                    params = call.get("params", {})
                    self.logger.info(f"Email agent decision: {tool_name} with {params}")
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
                self.logger.info(f"Email agent decision: {tool_name} with {params}")
                return await self._execute_tool(tool_name, params)

        except Exception as e:
            self.logger.error(f"Failed to parse LLM response: {response[:200]}")
            return {"error": f"Non ho capito la richiesta: {str(e)}"}

    async def _execute_tool(self, tool_name: str, params: dict) -> dict:
        """Execute the selected tool with given parameters."""

        if tool_name == "get_inbox":
            return await self._tool_get_inbox(params)
        elif tool_name == "get_email":
            return await self._tool_get_email(params)
        elif tool_name == "send_email":
            return await self._tool_send_email(params)
        elif tool_name == "reply_email":
            return await self._tool_reply_email(params)
        elif tool_name == "create_draft":
            return await self._tool_create_draft(params)
        elif tool_name == "search_emails":
            return await self._tool_search_emails(params)
        else:
            return {"error": f"Tool sconosciuto: {tool_name}"}

    async def _tool_get_inbox(self, params: dict) -> dict:
        """Get inbox emails."""
        try:
            emails = gmail_client.get_inbox(
                max_results=params.get("max_results", 10),
                unread_only=params.get("unread_only", False),
                query=params.get("query")
            )

            # Summarize for response
            summaries = []
            for email in emails[:10]:
                summaries.append({
                    "id": email["id"],
                    "from": email["from"],
                    "subject": email["subject"],
                    "snippet": email["snippet"][:100] if email.get("snippet") else "",
                    "is_unread": email.get("is_unread", False)
                })

            return {
                "operation": "get_inbox",
                "emails": summaries,
                "count": len(summaries),
                "unread_count": sum(1 for e in summaries if e.get("is_unread"))
            }
        except Exception as e:
            self.logger.error(f"get_inbox failed: {e}")
            return {"error": f"Errore nel recupero email: {str(e)}"}

    async def _tool_get_email(self, params: dict) -> dict:
        """Get full email content."""
        try:
            message_id = params.get("message_id")
            email = gmail_client.get_email(message_id)

            return {
                "operation": "get_email",
                "email": email
            }
        except Exception as e:
            self.logger.error(f"get_email failed: {e}")
            return {"error": f"Errore nel recupero email: {str(e)}"}

    async def _tool_send_email(self, params: dict) -> dict:
        """Send an email."""
        try:
            to = params.get("to")
            subject = params.get("subject", "")
            body = params.get("body", "")

            if not to:
                return {"error": "Destinatario mancante"}

            result = gmail_client.send_email(to=to, subject=subject, body=body)

            return {
                "operation": "send_email",
                "result": result,
                "message": f"Email inviata a {to}"
            }
        except Exception as e:
            self.logger.error(f"send_email failed: {e}")
            return {"error": f"Errore nell'invio email: {str(e)}"}

    async def _tool_reply_email(self, params: dict) -> dict:
        """Reply to an email."""
        try:
            message_id = params.get("message_id")
            body = params.get("body", "")

            if not message_id:
                return {"error": "ID email mancante"}

            result = gmail_client.reply_email(message_id=message_id, body=body)

            return {
                "operation": "reply_email",
                "result": result,
                "message": "Risposta inviata"
            }
        except Exception as e:
            self.logger.error(f"reply_email failed: {e}")
            return {"error": f"Errore nella risposta: {str(e)}"}

    async def _tool_create_draft(self, params: dict) -> dict:
        """Create an email draft."""
        try:
            to = params.get("to", "")
            subject = params.get("subject", "")
            body = params.get("body", "")

            result = gmail_client.create_draft(to=to, subject=subject, body=body)

            return {
                "operation": "create_draft",
                "result": result,
                "message": f"Bozza creata con oggetto '{subject}'"
            }
        except Exception as e:
            self.logger.error(f"create_draft failed: {e}")
            return {"error": f"Errore nella creazione bozza: {str(e)}"}

    async def _tool_search_emails(self, params: dict) -> dict:
        """Search emails."""
        try:
            query = params.get("query", "")
            max_results = params.get("max_results", 10)

            emails = gmail_client.search_emails(query=query, max_results=max_results)

            summaries = []
            for email in emails:
                summaries.append({
                    "id": email["id"],
                    "from": email["from"],
                    "subject": email["subject"],
                    "snippet": email["snippet"][:100] if email.get("snippet") else ""
                })

            return {
                "operation": "search_emails",
                "query": query,
                "emails": summaries,
                "count": len(summaries)
            }
        except Exception as e:
            self.logger.error(f"search_emails failed: {e}")
            return {"error": f"Errore nella ricerca: {str(e)}"}


# Singleton
email_agent = EmailAgent()
