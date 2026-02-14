"""Resolve Telegram IDs to Supabase Auth UUIDs and vice versa."""

import time
from collections import OrderedDict

from jarvis.db.supabase_client import get_db, run_db
from jarvis.utils.logging import get_logger

logger = get_logger(__name__)

_CACHE_TTL = 300  # 5 minutes
_CACHE_MAX = 1000


class _LRUCache:
    """Simple LRU cache with TTL."""

    def __init__(self, max_size: int = _CACHE_MAX, ttl: int = _CACHE_TTL):
        self._data: OrderedDict[str, tuple[object, float]] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl

    def get(self, key: str):
        entry = self._data.get(key)
        if entry is None:
            return None
        value, ts = entry
        if time.monotonic() - ts > self._ttl:
            del self._data[key]
            return None
        self._data.move_to_end(key)
        return value

    def set(self, key: str, value: object):
        self._data[key] = (value, time.monotonic())
        self._data.move_to_end(key)
        if len(self._data) > self._max_size:
            self._data.popitem(last=False)

    def invalidate(self, key: str):
        self._data.pop(key, None)


class UserResolver:
    """Resolve between Telegram IDs and Supabase Auth UUIDs."""

    def __init__(self):
        self._tg_to_uuid = _LRUCache()
        self._uuid_to_tg = _LRUCache()

    async def resolve_telegram_id(self, telegram_id: int) -> str | None:
        """Resolve a Telegram ID to a Supabase Auth UUID.

        Returns the UUID string or None if no profile is linked.
        """
        cache_key = str(telegram_id)
        cached = self._tg_to_uuid.get(cache_key)
        if cached is not None:
            return cached

        try:
            result = await run_db(
                lambda: get_db().rpc(
                    "resolve_telegram_id",
                    {"p_telegram_id": telegram_id},
                ).execute()
            )
            uuid_val = result.data
            if uuid_val:
                self._tg_to_uuid.set(cache_key, uuid_val)
                self._uuid_to_tg.set(uuid_val, telegram_id)
                return uuid_val
        except Exception as e:
            logger.error(f"Failed to resolve telegram_id {telegram_id}: {e}")

        return None

    async def resolve_uuid_to_telegram(self, user_id: str) -> int | None:
        """Resolve a Supabase Auth UUID to a Telegram ID.

        Returns the Telegram ID (int) or None if no Telegram is linked.
        """
        cached = self._uuid_to_tg.get(user_id)
        if cached is not None:
            return cached

        try:
            result = await run_db(
                lambda: get_db()
                .table("user_profiles")
                .select("telegram_id")
                .eq("id", user_id)
                .maybe_single()
                .execute()
            )
            if result.data and result.data.get("telegram_id"):
                tg_id = result.data["telegram_id"]
                self._uuid_to_tg.set(user_id, tg_id)
                self._tg_to_uuid.set(str(tg_id), user_id)
                return tg_id
        except Exception as e:
            logger.error(f"Failed to resolve UUID {user_id} to telegram_id: {e}")

        return None

    def invalidate_telegram(self, telegram_id: int):
        """Invalidate cache for a Telegram ID (e.g. after linking)."""
        cache_key = str(telegram_id)
        uuid_val = self._tg_to_uuid.get(cache_key)
        self._tg_to_uuid.invalidate(cache_key)
        if uuid_val:
            self._uuid_to_tg.invalidate(uuid_val)

    def invalidate_uuid(self, user_id: str):
        """Invalidate cache for a UUID."""
        tg_id = self._uuid_to_tg.get(user_id)
        self._uuid_to_tg.invalidate(user_id)
        if tg_id:
            self._tg_to_uuid.invalidate(str(tg_id))


# Singleton
user_resolver = UserResolver()
