"""Knowledge Graph Agent - Structured queries about people, organizations, and relationships."""

import json
from typing import Any
from jarvis.agents.base import BaseAgent
from jarvis.core.state import JarvisState
from jarvis.core.knowledge_graph import knowledge_graph
from jarvis.db.kg_repository import (
    KGEntityRepository,
    KGRelationshipRepository,
    KGAliasRepository
)
from jarvis.integrations.gemini import gemini

# Tool definitions for the LLM
KG_TOOLS = [
    {
        "name": "get_entity_info",
        "description": "Ottieni informazioni dettagliate su una persona, organizzazione, progetto o luogo specifico",
        "parameters": {
            "entity_name": "Nome dell'entita da cercare (es. 'Marco Rossi', 'Acme Corp')"
        }
    },
    {
        "name": "list_entities",
        "description": "Elenca tutte le entita conosciute di un certo tipo",
        "parameters": {
            "entity_type": "Tipo di entita: 'person', 'organization', 'project', 'location', 'event' (opzionale, default: tutti)"
        }
    },
    {
        "name": "find_colleagues",
        "description": "Trova i colleghi di una persona (persone che lavorano nella stessa organizzazione)",
        "parameters": {
            "person_name": "Nome della persona di cui cercare i colleghi"
        }
    },
    {
        "name": "get_relationships",
        "description": "Ottieni tutte le relazioni di una specifica entita",
        "parameters": {
            "entity_name": "Nome dell'entita di cui cercare le relazioni"
        }
    },
    {
        "name": "search_entities",
        "description": "Cerca entita per nome o parte del nome",
        "parameters": {
            "query": "Testo da cercare nel nome delle entita",
            "entity_type": "Filtra per tipo (opzionale): 'person', 'organization', 'project', 'location', 'event'"
        }
    }
]

AGENT_SYSTEM_PROMPT = """Sei un agente che gestisce il Knowledge Graph dell'utente. Il tuo compito e rispondere a domande su persone, organizzazioni, progetti e le loro relazioni.

TOOL DISPONIBILI:
{tools}

REGOLE:
1. Analizza la richiesta e decidi quale tool usare
2. Per domande su una persona specifica → usa get_entity_info
3. Per "chi sono i miei colleghi/contatti" → usa list_entities con entity_type="person" o find_colleagues
4. Per "per chi lavora X" o relazioni → usa get_relationships
5. Per cercare qualcuno di cui non si conosce il nome completo → usa search_entities

Rispondi SOLO con un JSON valido nel formato:
{{"tool": "nome_tool", "params": {{...}}}}

ESEMPI:
- "chi e Marco Rossi?" → {{"tool": "get_entity_info", "params": {{"entity_name": "Marco Rossi"}}}}
- "chi sono i miei colleghi?" → {{"tool": "list_entities", "params": {{"entity_type": "person"}}}}
- "colleghi di Marco" → {{"tool": "find_colleagues", "params": {{"person_name": "Marco"}}}}
- "per chi lavora Giovanni?" → {{"tool": "get_relationships", "params": {{"entity_name": "Giovanni"}}}}
- "conosco qualcuno che si chiama Luca?" → {{"tool": "search_entities", "params": {{"query": "Luca", "entity_type": "person"}}}}

Rispondi SOLO con il JSON, nient'altro."""


class KnowledgeGraphAgent(BaseAgent):
    """Agent for querying the knowledge graph."""

    name = "kg"
    resource_type = None  # No caching for KG queries

    async def _execute(self, state: JarvisState) -> Any:
        """Execute knowledge graph queries using LLM reasoning."""
        user_id = state["user_id"]
        user_input = state.get("enriched_input", state["current_input"])

        # Format tools for prompt
        tools_str = json.dumps(KG_TOOLS, indent=2, ensure_ascii=False)

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
            tool_name = decision.get("tool")
            params = decision.get("params", {})

            self.logger.info(f"KG agent decision: {tool_name} with {params}")

            return await self._execute_tool(user_id, tool_name, params)

        except Exception as e:
            self.logger.error(f"Failed to parse LLM response: {response[:200]}")
            return {"error": f"Non ho capito la richiesta: {str(e)}"}

    async def _execute_tool(self, user_id: str, tool_name: str, params: dict) -> dict:
        """Execute the selected tool with given parameters."""

        if tool_name == "get_entity_info":
            return await self._tool_get_entity_info(user_id, params)
        elif tool_name == "list_entities":
            return await self._tool_list_entities(user_id, params)
        elif tool_name == "find_colleagues":
            return await self._tool_find_colleagues(user_id, params)
        elif tool_name == "get_relationships":
            return await self._tool_get_relationships(user_id, params)
        elif tool_name == "search_entities":
            return await self._tool_search_entities(user_id, params)
        else:
            return {"error": f"Tool sconosciuto: {tool_name}"}

    async def _tool_get_entity_info(self, user_id: str, params: dict) -> dict:
        """Get detailed information about an entity."""
        try:
            entity_name = params.get("entity_name", "")
            if not entity_name:
                return {"error": "Nome entita mancante"}

            info = await knowledge_graph.get_entity_info(user_id, entity_name)

            if not info:
                return {
                    "operation": "get_entity_info",
                    "query": entity_name,
                    "found": False,
                    "message": f"Non conosco nessuna entita chiamata '{entity_name}'"
                }

            entity = info["entity"]
            relationships = info["relationships"]
            aliases = info["aliases"]

            # Format relationships for output
            rel_formatted = []
            for rel in relationships:
                direction = rel.get("direction", "")
                rel_type = rel.get("rel_type", "")
                related_name = rel.get("related_entity_name", "")
                related_type = rel.get("related_entity_type", "")

                if direction == "outgoing":
                    rel_formatted.append(f"{rel_type} -> {related_name} ({related_type})")
                else:
                    rel_formatted.append(f"{related_name} ({related_type}) -> {rel_type}")

            return {
                "operation": "get_entity_info",
                "found": True,
                "entity": {
                    "name": entity["canonical_name"],
                    "type": entity["entity_type"],
                    "properties": entity.get("properties", {}),
                    "confidence": entity.get("confidence", 0),
                    "mention_count": entity.get("mention_count", 0)
                },
                "relationships": rel_formatted,
                "aliases": aliases,
                "message": f"Informazioni su {entity['canonical_name']}"
            }
        except Exception as e:
            self.logger.error(f"get_entity_info failed: {e}")
            return {"error": f"Errore nel recupero informazioni: {str(e)}"}

    async def _tool_list_entities(self, user_id: str, params: dict) -> dict:
        """List all entities of a given type."""
        try:
            entity_type = params.get("entity_type")

            # Validate entity type if provided
            valid_types = ['person', 'organization', 'project', 'location', 'event']
            if entity_type and entity_type not in valid_types:
                return {"error": f"Tipo entita non valido. Validi: {', '.join(valid_types)}"}

            entities = await KGEntityRepository.get_all_entities(
                user_id=user_id,
                entity_type=entity_type,
                limit=50
            )

            if not entities:
                type_str = f" di tipo '{entity_type}'" if entity_type else ""
                return {
                    "operation": "list_entities",
                    "filter_type": entity_type,
                    "entities": [],
                    "count": 0,
                    "message": f"Non ho memorizzato nessuna entita{type_str}"
                }

            # Format entities for output
            formatted = []
            for e in entities:
                entry = {
                    "name": e["canonical_name"],
                    "type": e["entity_type"],
                    "properties": e.get("properties", {}),
                    "mentions": e.get("mention_count", 0)
                }
                formatted.append(entry)

            type_str = f" di tipo '{entity_type}'" if entity_type else ""
            return {
                "operation": "list_entities",
                "filter_type": entity_type,
                "entities": formatted,
                "count": len(formatted),
                "message": f"Trovate {len(formatted)} entita{type_str}"
            }
        except Exception as e:
            self.logger.error(f"list_entities failed: {e}")
            return {"error": f"Errore nel recupero entita: {str(e)}"}

    async def _tool_find_colleagues(self, user_id: str, params: dict) -> dict:
        """Find colleagues of a person."""
        try:
            person_name = params.get("person_name", "")
            if not person_name:
                return {"error": "Nome persona mancante"}

            colleagues = await knowledge_graph.find_colleagues(user_id, person_name)

            if not colleagues:
                return {
                    "operation": "find_colleagues",
                    "query": person_name,
                    "colleagues": [],
                    "count": 0,
                    "message": f"Non ho trovato colleghi di '{person_name}'. Potrebbe non lavorare in un'organizzazione nota, o non avere colleghi registrati."
                }

            # Format colleagues
            formatted = []
            for c in colleagues:
                formatted.append({
                    "name": c["colleague_name"],
                    "organization": c["shared_org_name"],
                    "properties": c.get("colleague_properties", {})
                })

            return {
                "operation": "find_colleagues",
                "query": person_name,
                "colleagues": formatted,
                "count": len(formatted),
                "message": f"Trovati {len(formatted)} colleghi di '{person_name}'"
            }
        except Exception as e:
            self.logger.error(f"find_colleagues failed: {e}")
            return {"error": f"Errore nella ricerca colleghi: {str(e)}"}

    async def _tool_get_relationships(self, user_id: str, params: dict) -> dict:
        """Get all relationships of an entity."""
        try:
            entity_name = params.get("entity_name", "")
            if not entity_name:
                return {"error": "Nome entita mancante"}

            # First find the entity
            results = await KGEntityRepository.search_by_name(
                user_id=user_id,
                query=entity_name,
                limit=1
            )

            if not results:
                return {
                    "operation": "get_relationships",
                    "query": entity_name,
                    "found": False,
                    "message": f"Non conosco nessuna entita chiamata '{entity_name}'"
                }

            entity = results[0]
            relationships = await KGRelationshipRepository.get_entity_relationships(entity["id"])

            if not relationships:
                return {
                    "operation": "get_relationships",
                    "query": entity_name,
                    "found": True,
                    "entity_type": entity["entity_type"],
                    "relationships": [],
                    "message": f"'{entity['canonical_name']}' non ha relazioni registrate"
                }

            # Format relationships
            formatted = []
            for rel in relationships:
                entry = {
                    "direction": rel.get("direction", ""),
                    "type": rel.get("rel_type", ""),
                    "related_entity": rel.get("related_entity_name", ""),
                    "related_type": rel.get("related_entity_type", ""),
                    "is_current": rel.get("is_current", True)
                }
                formatted.append(entry)

            return {
                "operation": "get_relationships",
                "query": entity_name,
                "found": True,
                "entity": {
                    "name": entity["canonical_name"],
                    "type": entity["entity_type"]
                },
                "relationships": formatted,
                "count": len(formatted),
                "message": f"Trovate {len(formatted)} relazioni per '{entity['canonical_name']}'"
            }
        except Exception as e:
            self.logger.error(f"get_relationships failed: {e}")
            return {"error": f"Errore nel recupero relazioni: {str(e)}"}

    async def _tool_search_entities(self, user_id: str, params: dict) -> dict:
        """Search entities by name."""
        try:
            query = params.get("query", "")
            entity_type = params.get("entity_type")

            if not query:
                return {"error": "Query di ricerca mancante"}

            # Validate entity type if provided
            valid_types = ['person', 'organization', 'project', 'location', 'event']
            if entity_type and entity_type not in valid_types:
                entity_type = None

            results = await KGEntityRepository.search_by_name(
                user_id=user_id,
                query=query,
                entity_type=entity_type,
                limit=10
            )

            if not results:
                type_str = f" di tipo '{entity_type}'" if entity_type else ""
                return {
                    "operation": "search_entities",
                    "query": query,
                    "filter_type": entity_type,
                    "entities": [],
                    "count": 0,
                    "message": f"Nessuna entita{type_str} trovata con '{query}'"
                }

            # Format results
            formatted = []
            for r in results:
                formatted.append({
                    "name": r["canonical_name"],
                    "type": r["entity_type"],
                    "match_type": r.get("match_type", "unknown"),
                    "confidence": r.get("confidence", 0)
                })

            type_str = f" di tipo '{entity_type}'" if entity_type else ""
            return {
                "operation": "search_entities",
                "query": query,
                "filter_type": entity_type,
                "entities": formatted,
                "count": len(formatted),
                "message": f"Trovate {len(formatted)} entita{type_str} con '{query}'"
            }
        except Exception as e:
            self.logger.error(f"search_entities failed: {e}")
            return {"error": f"Errore nella ricerca: {str(e)}"}


# Singleton
kg_agent = KnowledgeGraphAgent()
