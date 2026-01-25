from typing import Optional
from datetime import datetime
from jarvis.db.supabase_client import get_db
from jarvis.utils.logging import get_logger

logger = get_logger(__name__)


class ChatRepository:
    """Repository per gestione chat history."""

    @staticmethod
    async def save_message(
        user_id: str,
        role: str,
        content: str,
        metadata: dict = None
    ) -> dict:
        db = get_db()
        result = db.table("chat_history").insert({
            "user_id": user_id,
            "role": role,
            "content": content,
            "metadata": metadata or {}
        }).execute()
        return result.data[0] if result.data else None

    @staticmethod
    async def get_recent_messages(
        user_id: str,
        limit: int = 20
    ) -> list[dict]:
        db = get_db()
        result = db.table("chat_history") \
            .select("*") \
            .eq("user_id", user_id) \
            .order("created_at", desc=True) \
            .limit(limit) \
            .execute()
        return list(reversed(result.data)) if result.data else []


class MemoryRepository:
    """Repository per gestione memory facts."""

    @staticmethod
    async def save_fact(
        user_id: str,
        fact: str,
        category: str,
        embedding: list[float],
        importance: float = 0.5,
        source_message_id: str = None
    ) -> dict:
        db = get_db()
        result = db.table("memory_facts").insert({
            "user_id": user_id,
            "fact": fact,
            "category": category,
            "embedding": embedding,
            "importance": importance,
            "source_message_id": source_message_id
        }).execute()
        return result.data[0] if result.data else None

    @staticmethod
    async def search_facts(
        user_id: str,
        query_embedding: list[float],
        threshold: float = 0.7,
        limit: int = 5
    ) -> list[dict]:
        db = get_db()
        result = db.rpc("match_memory_facts", {
            "query_embedding": query_embedding,
            "match_user_id": user_id,
            "match_threshold": threshold,
            "match_count": limit
        }).execute()
        return result.data if result.data else []

    @staticmethod
    async def get_all_facts(user_id: str) -> list[dict]:
        db = get_db()
        result = db.table("memory_facts") \
            .select("id, fact, category, importance, created_at") \
            .eq("user_id", user_id) \
            .order("created_at", desc=True) \
            .execute()
        return result.data if result.data else []


class RAGRepository:
    """Repository per gestione RAG documents."""

    @staticmethod
    async def save_document(
        user_id: str,
        title: str,
        content: str,
        embedding: list[float],
        chunk_index: int = 0,
        metadata: dict = None,
        source_url: str = None
    ) -> dict:
        db = get_db()
        result = db.table("rag_documents").insert({
            "user_id": user_id,
            "title": title,
            "content": content,
            "embedding": embedding,
            "chunk_index": chunk_index,
            "metadata": metadata or {},
            "source_url": source_url
        }).execute()
        return result.data[0] if result.data else None

    @staticmethod
    async def search_documents(
        user_id: str,
        query_embedding: list[float],
        threshold: float = 0.7,
        limit: int = 5
    ) -> list[dict]:
        db = get_db()
        result = db.rpc("match_rag_documents", {
            "query_embedding": query_embedding,
            "match_user_id": user_id,
            "match_threshold": threshold,
            "match_count": limit
        }).execute()
        return result.data if result.data else []

    @staticmethod
    async def delete_document(document_id: str) -> bool:
        db = get_db()
        result = db.table("rag_documents") \
            .delete() \
            .eq("id", document_id) \
            .execute()
        return len(result.data) > 0 if result.data else False


class UserPreferencesRepository:
    """Repository per gestione preferenze utente."""

    @staticmethod
    async def get_or_create(user_id: str) -> dict:
        db = get_db()
        result = db.table("user_preferences") \
            .select("*") \
            .eq("user_id", user_id) \
            .execute()

        if result.data:
            return result.data[0]

        # Create default preferences
        new_prefs = db.table("user_preferences").insert({
            "user_id": user_id
        }).execute()
        return new_prefs.data[0] if new_prefs.data else None

    @staticmethod
    async def update(user_id: str, updates: dict) -> dict:
        db = get_db()
        updates["updated_at"] = datetime.utcnow().isoformat()
        result = db.table("user_preferences") \
            .update(updates) \
            .eq("user_id", user_id) \
            .execute()
        return result.data[0] if result.data else None
