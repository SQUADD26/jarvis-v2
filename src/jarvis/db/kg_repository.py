"""Knowledge Graph Repository - CRUD operations for entities and relationships."""

from typing import Optional, Literal
from datetime import datetime
from jarvis.db.supabase_client import get_db
from jarvis.utils.logging import get_logger

logger = get_logger(__name__)

EntityType = Literal['person', 'organization', 'project', 'location', 'event']
RelationshipType = Literal[
    'reports_to', 'collaborates_with', 'knows', 'is_family_of',
    'works_for', 'is_client_of', 'is_partner_of', 'owns',
    'leads', 'works_on', 'created',
    'located_in', 'lives_in',
    'attended', 'organized',
    'subsidiary_of', 'competes_with',
    'related_to'
]


class KGEntityRepository:
    """Repository for Knowledge Graph entities."""

    @staticmethod
    async def create_entity(
        user_id: str,
        canonical_name: str,
        entity_type: EntityType,
        properties: dict = None,
        embedding: list[float] = None,
        confidence: float = 0.5,
        source_type: str = 'conversation',
        source_id: str = None
    ) -> Optional[dict]:
        """Create a new entity."""
        db = get_db()
        data = {
            "user_id": user_id,
            "canonical_name": canonical_name,
            "entity_type": entity_type,
            "properties": properties or {},
            "confidence": confidence,
            "source_type": source_type,
            "source_id": source_id
        }
        if embedding:
            data["embedding"] = embedding

        try:
            result = db.table("kg_entities").insert(data).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            # Handle unique constraint violation (entity already exists)
            if "duplicate key" in str(e).lower() or "unique constraint" in str(e).lower():
                logger.debug(f"Entity already exists: {canonical_name} ({entity_type})")
                return None
            raise

    @staticmethod
    async def get_entity(entity_id: str) -> Optional[dict]:
        """Get entity by ID."""
        db = get_db()
        result = db.table("kg_entities") \
            .select("*") \
            .eq("id", entity_id) \
            .execute()
        return result.data[0] if result.data else None

    @staticmethod
    async def get_entity_by_name(
        user_id: str,
        canonical_name: str,
        entity_type: EntityType = None
    ) -> Optional[dict]:
        """Get entity by canonical name (case-insensitive)."""
        db = get_db()
        query = db.table("kg_entities") \
            .select("*") \
            .eq("user_id", user_id) \
            .ilike("canonical_name", canonical_name)

        if entity_type:
            query = query.eq("entity_type", entity_type)

        result = query.limit(1).execute()
        return result.data[0] if result.data else None

    @staticmethod
    async def update_entity(
        entity_id: str,
        updates: dict
    ) -> Optional[dict]:
        """Update entity properties."""
        db = get_db()
        updates["updated_at"] = datetime.utcnow().isoformat()
        result = db.table("kg_entities") \
            .update(updates) \
            .eq("id", entity_id) \
            .execute()
        return result.data[0] if result.data else None

    @staticmethod
    async def update_mention(entity_id: str) -> None:
        """Update mention count and timestamp for entity."""
        db = get_db()
        db.rpc("update_entity_mention", {"p_entity_id": entity_id}).execute()

    @staticmethod
    async def merge_properties(
        entity_id: str,
        new_properties: dict
    ) -> Optional[dict]:
        """Merge new properties into existing entity properties."""
        # Get current entity
        entity = await KGEntityRepository.get_entity(entity_id)
        if not entity:
            return None

        # Merge properties (new values overwrite existing)
        merged = {**entity.get("properties", {}), **new_properties}

        return await KGEntityRepository.update_entity(entity_id, {"properties": merged})

    @staticmethod
    async def search_by_embedding(
        user_id: str,
        query_embedding: list[float],
        threshold: float = 0.7,
        limit: int = 5,
        entity_type: EntityType = None
    ) -> list[dict]:
        """Vector similarity search for entities."""
        db = get_db()
        params = {
            "query_embedding": query_embedding,
            "match_user_id": user_id,
            "match_threshold": threshold,
            "match_count": limit
        }
        if entity_type:
            params["filter_entity_type"] = entity_type

        result = db.rpc("match_kg_entities", params).execute()
        return result.data if result.data else []

    @staticmethod
    async def search_by_name(
        user_id: str,
        query: str,
        entity_type: EntityType = None,
        limit: int = 10
    ) -> list[dict]:
        """Search entities by name or alias."""
        db = get_db()
        params = {
            "p_user_id": user_id,
            "p_query": query,
            "p_limit": limit
        }
        if entity_type:
            params["p_entity_type"] = entity_type

        result = db.rpc("search_kg_entities", params).execute()
        return result.data if result.data else []

    @staticmethod
    async def get_all_entities(
        user_id: str,
        entity_type: EntityType = None,
        limit: int = 100
    ) -> list[dict]:
        """Get all entities for a user."""
        db = get_db()
        query = db.table("kg_entities") \
            .select("id, canonical_name, entity_type, properties, confidence, mention_count, last_mentioned_at") \
            .eq("user_id", user_id) \
            .order("last_mentioned_at", desc=True) \
            .limit(limit)

        if entity_type:
            query = query.eq("entity_type", entity_type)

        result = query.execute()
        return result.data if result.data else []

    @staticmethod
    async def delete_entity(entity_id: str) -> bool:
        """Delete entity (cascades to aliases and relationships)."""
        db = get_db()
        result = db.table("kg_entities") \
            .delete() \
            .eq("id", entity_id) \
            .execute()
        return len(result.data) > 0 if result.data else False


class KGAliasRepository:
    """Repository for entity aliases."""

    @staticmethod
    async def add_alias(
        entity_id: str,
        alias: str,
        confidence: float = 0.8
    ) -> Optional[dict]:
        """Add an alias for an entity."""
        db = get_db()
        try:
            result = db.table("kg_entity_aliases").insert({
                "entity_id": entity_id,
                "alias": alias,
                "confidence": confidence
            }).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            if "duplicate key" in str(e).lower() or "unique constraint" in str(e).lower():
                logger.debug(f"Alias already exists: {alias}")
                return None
            raise

    @staticmethod
    async def get_aliases(entity_id: str) -> list[dict]:
        """Get all aliases for an entity."""
        db = get_db()
        result = db.table("kg_entity_aliases") \
            .select("*") \
            .eq("entity_id", entity_id) \
            .execute()
        return result.data if result.data else []

    @staticmethod
    async def find_entity_by_alias(
        user_id: str,
        alias: str
    ) -> Optional[dict]:
        """Find entity by one of its aliases."""
        db = get_db()
        # First search in aliases table
        result = db.table("kg_entity_aliases") \
            .select("entity_id, kg_entities(*)") \
            .ilike("alias", alias) \
            .execute()

        if result.data:
            # Get the first matching entity that belongs to the user
            for item in result.data:
                entity = item.get("kg_entities")
                if entity and entity.get("user_id") == user_id:
                    return entity

        # Fallback: search by canonical name
        return await KGEntityRepository.get_entity_by_name(user_id, alias)

    @staticmethod
    async def delete_alias(entity_id: str, alias: str) -> bool:
        """Delete an alias."""
        db = get_db()
        result = db.table("kg_entity_aliases") \
            .delete() \
            .eq("entity_id", entity_id) \
            .ilike("alias", alias) \
            .execute()
        return len(result.data) > 0 if result.data else False


class KGRelationshipRepository:
    """Repository for entity relationships."""

    @staticmethod
    async def create_relationship(
        user_id: str,
        source_entity_id: str,
        target_entity_id: str,
        relationship_type: RelationshipType,
        properties: dict = None,
        is_current: bool = True,
        started_at: str = None,
        confidence: float = 0.5,
        source_type: str = 'conversation',
        source_id: str = None
    ) -> Optional[dict]:
        """Create a relationship between two entities."""
        db = get_db()
        data = {
            "user_id": user_id,
            "source_entity_id": source_entity_id,
            "target_entity_id": target_entity_id,
            "relationship_type": relationship_type,
            "properties": properties or {},
            "is_current": is_current,
            "confidence": confidence,
            "source_type": source_type,
            "source_id": source_id
        }
        if started_at:
            data["started_at"] = started_at

        try:
            result = db.table("kg_relationships").insert(data).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            if "duplicate key" in str(e).lower() or "unique constraint" in str(e).lower():
                logger.debug(f"Relationship already exists: {source_entity_id} --[{relationship_type}]--> {target_entity_id}")
                return None
            raise

    @staticmethod
    async def get_relationship(relationship_id: str) -> Optional[dict]:
        """Get relationship by ID."""
        db = get_db()
        result = db.table("kg_relationships") \
            .select("*") \
            .eq("id", relationship_id) \
            .execute()
        return result.data[0] if result.data else None

    @staticmethod
    async def get_entity_relationships(
        entity_id: str,
        include_inactive: bool = False
    ) -> list[dict]:
        """Get all relationships for an entity (both directions)."""
        db = get_db()
        result = db.rpc("get_entity_relationships", {
            "p_entity_id": entity_id,
            "p_include_inactive": include_inactive
        }).execute()
        return result.data if result.data else []

    @staticmethod
    async def find_relationship(
        user_id: str,
        source_entity_id: str,
        target_entity_id: str,
        relationship_type: RelationshipType = None
    ) -> Optional[dict]:
        """Find existing relationship between two entities."""
        db = get_db()
        query = db.table("kg_relationships") \
            .select("*") \
            .eq("user_id", user_id) \
            .eq("source_entity_id", source_entity_id) \
            .eq("target_entity_id", target_entity_id)

        if relationship_type:
            query = query.eq("relationship_type", relationship_type)

        result = query.limit(1).execute()
        return result.data[0] if result.data else None

    @staticmethod
    async def update_relationship(
        relationship_id: str,
        updates: dict
    ) -> Optional[dict]:
        """Update relationship properties."""
        db = get_db()
        updates["updated_at"] = datetime.utcnow().isoformat()
        result = db.table("kg_relationships") \
            .update(updates) \
            .eq("id", relationship_id) \
            .execute()
        return result.data[0] if result.data else None

    @staticmethod
    async def end_relationship(
        relationship_id: str,
        ended_at: str = None
    ) -> Optional[dict]:
        """Mark a relationship as ended (no longer current)."""
        db = get_db()
        updates = {
            "is_current": False,
            "ended_at": ended_at or datetime.utcnow().date().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        result = db.table("kg_relationships") \
            .update(updates) \
            .eq("id", relationship_id) \
            .execute()
        return result.data[0] if result.data else None

    @staticmethod
    async def delete_relationship(relationship_id: str) -> bool:
        """Delete a relationship."""
        db = get_db()
        result = db.table("kg_relationships") \
            .delete() \
            .eq("id", relationship_id) \
            .execute()
        return len(result.data) > 0 if result.data else False

    @staticmethod
    async def find_colleagues(
        user_id: str,
        person_entity_id: str
    ) -> list[dict]:
        """Find colleagues (people who work for same organization)."""
        db = get_db()
        result = db.rpc("find_colleagues", {
            "p_user_id": user_id,
            "p_person_entity_id": person_entity_id
        }).execute()
        return result.data if result.data else []


class KGContextRepository:
    """Repository for loading entity context for prompt injection."""

    @staticmethod
    async def get_entities_with_context(
        user_id: str,
        entity_ids: list[str],
        max_relationships: int = 3
    ) -> list[dict]:
        """Get entities with their relationships for context injection."""
        db = get_db()
        result = db.rpc("get_entities_with_context", {
            "p_user_id": user_id,
            "p_entity_ids": entity_ids,
            "p_max_relationships": max_relationships
        }).execute()
        return result.data if result.data else []

    @staticmethod
    async def get_relevant_entities(
        user_id: str,
        query_embedding: list[float],
        limit: int = 5,
        threshold: float = 0.65
    ) -> list[dict]:
        """Get relevant entities with context for a query."""
        # First, get matching entities
        entities = await KGEntityRepository.search_by_embedding(
            user_id=user_id,
            query_embedding=query_embedding,
            threshold=threshold,
            limit=limit
        )

        if not entities:
            return []

        # Get full context for matched entities
        entity_ids = [e["id"] for e in entities]
        return await KGContextRepository.get_entities_with_context(
            user_id=user_id,
            entity_ids=entity_ids,
            max_relationships=3
        )
