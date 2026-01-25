from typing import Optional, Literal
from datetime import datetime
from jarvis.db.supabase_client import get_db
from jarvis.utils.logging import get_logger

logger = get_logger(__name__)

TaskStatus = Literal["pending", "claimed", "running", "completed", "failed", "cancelled"]
TaskType = Literal["reminder", "scheduled_check", "long_running"]


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


class TaskRepository:
    """Repository per gestione task queue (proattività e parallelismo)."""

    @staticmethod
    async def enqueue(
        user_id: str,
        task_type: TaskType,
        payload: dict,
        scheduled_at: datetime = None,
        priority: int = 5
    ) -> dict:
        """Accoda un nuovo task."""
        db = get_db()
        data = {
            "user_id": user_id,
            "task_type": task_type,
            "payload": payload,
            "priority": priority
        }
        if scheduled_at:
            data["scheduled_at"] = scheduled_at.isoformat()

        result = db.table("task_queue").insert(data).execute()
        return result.data[0] if result.data else None

    @staticmethod
    async def claim_next(worker_id: str) -> Optional[dict]:
        """Claim atomico del prossimo task disponibile."""
        db = get_db()
        result = db.rpc("claim_next_task", {"p_worker_id": worker_id}).execute()
        return result.data if result.data else None

    @staticmethod
    async def start_task(task_id: str) -> dict:
        """Marca un task come running."""
        db = get_db()
        result = db.table("task_queue") \
            .update({
                "status": "running",
                "started_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }) \
            .eq("id", task_id) \
            .execute()
        return result.data[0] if result.data else None

    @staticmethod
    async def complete_task(task_id: str, result_data: dict = None) -> dict:
        """Completa un task con successo."""
        db = get_db()
        result = db.rpc("complete_task", {
            "p_task_id": task_id,
            "p_result": result_data
        }).execute()
        return result.data if result.data else None

    @staticmethod
    async def fail_task(task_id: str, error: str) -> dict:
        """Marca un task come fallito (con retry automatico se possibile)."""
        db = get_db()
        result = db.rpc("fail_task", {
            "p_task_id": task_id,
            "p_error": error
        }).execute()
        return result.data if result.data else None

    @staticmethod
    async def cancel_task(task_id: str) -> dict:
        """Cancella un task pendente."""
        db = get_db()
        result = db.table("task_queue") \
            .update({
                "status": "cancelled",
                "updated_at": datetime.utcnow().isoformat()
            }) \
            .eq("id", task_id) \
            .in_("status", ["pending", "claimed"]) \
            .execute()
        return result.data[0] if result.data else None

    @staticmethod
    async def get_user_tasks(
        user_id: str,
        status: TaskStatus = None,
        limit: int = 20
    ) -> list[dict]:
        """Recupera i task di un utente."""
        db = get_db()
        query = db.table("task_queue") \
            .select("*") \
            .eq("user_id", user_id) \
            .order("created_at", desc=True) \
            .limit(limit)

        if status:
            query = query.eq("status", status)

        result = query.execute()
        return result.data if result.data else []

    @staticmethod
    async def get_pending_count() -> int:
        """Conta i task pendenti (per monitoring)."""
        db = get_db()
        result = db.table("task_queue") \
            .select("id", count="exact") \
            .eq("status", "pending") \
            .execute()
        return result.count if result.count else 0

    @staticmethod
    async def get_task(task_id: str) -> Optional[dict]:
        """Recupera un singolo task."""
        db = get_db()
        result = db.table("task_queue") \
            .select("*") \
            .eq("id", task_id) \
            .execute()
        return result.data[0] if result.data else None

    @staticmethod
    async def cleanup_stale_tasks(timeout_minutes: int = 30) -> int:
        """Resetta task bloccati in stato 'claimed' o 'running' troppo a lungo."""
        db = get_db()
        result = db.rpc("cleanup_stale_tasks", {
            "p_timeout_minutes": timeout_minutes
        }).execute()
        return result.data if isinstance(result.data, int) else 0
