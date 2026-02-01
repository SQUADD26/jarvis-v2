"""Notion API integration - async httpx-based client."""

import asyncio
import httpx
from typing import Any, Optional
from jarvis.config import get_settings
from jarvis.db.redis_client import redis_client
from jarvis.utils.logging import get_logger

logger = get_logger(__name__)

NOTION_VERSION = "2022-06-28"
BASE_URL = "https://api.notion.com/v1"

# Redis cache TTLs
DATABASES_CACHE_TTL = 3600  # 1 hour
SCHEMA_CACHE_TTL = 3600  # 1 hour


class NotionClient:
    """Async Notion API client using httpx."""

    def __init__(self):
        settings = get_settings()
        self.api_key = settings.notion_api_key
        self._headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }

    async def _request(
        self,
        method: str,
        endpoint: str,
        json_data: dict = None,
        retries: int = 2,
    ) -> dict:
        """Central request method with rate limit handling."""
        url = f"{BASE_URL}{endpoint}"

        for attempt in range(retries + 1):
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method,
                    url,
                    headers=self._headers,
                    json=json_data,
                    timeout=30.0,
                )

                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", "2"))
                    logger.warning(f"Notion rate limited, retrying in {retry_after}s")
                    await asyncio.sleep(retry_after)
                    continue

                response.raise_for_status()
                return response.json()

        raise httpx.HTTPStatusError(
            "Rate limit exceeded after retries",
            request=response.request,
            response=response,
        )

    # ── Discovery & Schema ──────────────────────────────────────────

    async def discover_databases(self) -> list[dict]:
        """List all accessible databases, cached in Redis for 1h."""
        cache_key = "jarvis:notion:databases"
        cached = await redis_client.get(cache_key)
        if cached:
            return cached

        results = []
        start_cursor = None
        has_more = True

        while has_more:
            body = {"filter": {"value": "database", "property": "object"}, "page_size": 100}
            if start_cursor:
                body["start_cursor"] = start_cursor

            data = await self._request("POST", "/search", body)
            for db in data.get("results", []):
                title_parts = db.get("title", [])
                title = "".join(t.get("plain_text", "") for t in title_parts) or "Untitled"
                results.append({
                    "id": db["id"],
                    "title": title,
                    "url": db.get("url", ""),
                })

            has_more = data.get("has_more", False)
            start_cursor = data.get("next_cursor")

        await redis_client.set(cache_key, results, DATABASES_CACHE_TTL)
        return results

    async def get_database_schema(self, db_id: str) -> dict:
        """Get database properties schema, cached 1h."""
        cache_key = f"jarvis:notion:schema:{db_id}"
        cached = await redis_client.get(cache_key)
        if cached:
            return cached

        data = await self._request("GET", f"/databases/{db_id}")
        properties = {}
        for name, prop in data.get("properties", {}).items():
            prop_info = {"type": prop["type"], "name": name}
            if prop["type"] == "select":
                prop_info["options"] = [o["name"] for o in prop.get("select", {}).get("options", [])]
            elif prop["type"] == "multi_select":
                prop_info["options"] = [o["name"] for o in prop.get("multi_select", {}).get("options", [])]
            elif prop["type"] == "status":
                prop_info["options"] = [o["name"] for o in prop.get("status", {}).get("options", [])]
                prop_info["groups"] = [
                    {"name": g["name"], "option_ids": g.get("option_ids", [])}
                    for g in prop.get("status", {}).get("groups", [])
                ]
            properties[name] = prop_info

        schema = {"id": db_id, "properties": properties}
        await redis_client.set(cache_key, schema, SCHEMA_CACHE_TTL)
        return schema

    # ── Query & Search ──────────────────────────────────────────────

    async def query_database(
        self,
        db_id: str,
        filter_obj: dict = None,
        sorts: list = None,
        page_size: int = 100,
        max_pages: int = 5,
    ) -> list[dict]:
        """Query a database with pagination (up to max_pages * 100 results)."""
        results = []
        start_cursor = None

        for _ in range(max_pages):
            body: dict[str, Any] = {"page_size": min(page_size, 100)}
            if filter_obj:
                body["filter"] = filter_obj
            if sorts:
                body["sorts"] = sorts
            if start_cursor:
                body["start_cursor"] = start_cursor

            data = await self._request("POST", f"/databases/{db_id}/query", body)
            results.extend(self.format_page_properties(p) for p in data.get("results", []))

            if not data.get("has_more"):
                break
            start_cursor = data.get("next_cursor")

        return results

    async def search_pages(self, query: str) -> list[dict]:
        """Full-text search across all pages."""
        body = {"query": query, "page_size": 20}
        data = await self._request("POST", "/search", body)
        results = []
        for item in data.get("results", []):
            if item["object"] == "page":
                results.append(self.format_page_properties(item))
        return results

    async def get_page_title(self, page_id: str) -> str:
        """Get just the title of a page by ID."""
        data = await self._request("GET", f"/pages/{page_id}")
        for prop in data.get("properties", {}).values():
            if prop.get("type") == "title":
                return "".join(t.get("plain_text", "") for t in prop.get("title", []))
        return ""

    async def resolve_relation_titles(self, page_ids: list[str]) -> dict[str, str]:
        """Resolve a batch of page IDs to their titles. Returns {id: title}."""
        if not page_ids:
            return {}

        # Check Redis cache first
        cache_key = "jarvis:notion:page_titles"
        cached = await redis_client.get(cache_key) or {}

        missing = [pid for pid in page_ids if pid not in cached]
        if missing:
            # Fetch missing titles in parallel (max 10 concurrent)
            sem = asyncio.Semaphore(10)

            async def fetch(pid):
                async with sem:
                    try:
                        title = await self.get_page_title(pid)
                        return pid, title
                    except Exception:
                        return pid, ""

            results = await asyncio.gather(*(fetch(pid) for pid in set(missing)))
            for pid, title in results:
                cached[pid] = title

            # Cache for 1 hour
            await redis_client.set(cache_key, cached, 3600)

        return {pid: cached.get(pid, "") for pid in page_ids}

    # ── Create / Update / Archive ───────────────────────────────────

    async def create_page(self, db_id: str, properties: dict) -> dict:
        """Create a new page (task) in a database."""
        body = {
            "parent": {"database_id": db_id},
            "properties": properties,
        }
        data = await self._request("POST", "/pages", body)
        return self.format_page_properties(data)

    async def update_page(self, page_id: str, properties: dict) -> dict:
        """Update page properties."""
        data = await self._request("PATCH", f"/pages/{page_id}", {"properties": properties})
        return self.format_page_properties(data)

    async def archive_page(self, page_id: str) -> dict:
        """Archive (soft-delete) a page."""
        data = await self._request("PATCH", f"/pages/{page_id}", {"archived": True})
        return self.format_page_properties(data)

    # ── Property helpers ────────────────────────────────────────────

    @staticmethod
    def format_page_properties(page: dict) -> dict:
        """Flatten Notion's nested property format into a readable dict."""
        result = {
            "id": page["id"],
            "url": page.get("url", ""),
            "created_time": page.get("created_time", ""),
            "last_edited_time": page.get("last_edited_time", ""),
            "archived": page.get("archived", False),
        }

        for name, prop in page.get("properties", {}).items():
            ptype = prop.get("type", "")

            if ptype == "title":
                texts = prop.get("title", [])
                result[name] = "".join(t.get("plain_text", "") for t in texts)
            elif ptype == "rich_text":
                texts = prop.get("rich_text", [])
                result[name] = "".join(t.get("plain_text", "") for t in texts)
            elif ptype == "select":
                sel = prop.get("select")
                result[name] = sel["name"] if sel else None
            elif ptype == "multi_select":
                result[name] = [o["name"] for o in prop.get("multi_select", [])]
            elif ptype == "status":
                st = prop.get("status")
                result[name] = st["name"] if st else None
            elif ptype == "date":
                d = prop.get("date")
                if d:
                    result[name] = {"start": d.get("start"), "end": d.get("end")}
                else:
                    result[name] = None
            elif ptype == "checkbox":
                result[name] = prop.get("checkbox", False)
            elif ptype == "number":
                result[name] = prop.get("number")
            elif ptype == "url":
                result[name] = prop.get("url")
            elif ptype == "people":
                result[name] = [
                    p.get("name", p.get("id", ""))
                    for p in prop.get("people", [])
                ]
            elif ptype == "email":
                result[name] = prop.get("email")
            elif ptype == "phone_number":
                result[name] = prop.get("phone_number")
            elif ptype == "formula":
                formula = prop.get("formula", {})
                ftype = formula.get("type", "")
                result[name] = formula.get(ftype)
            elif ptype == "relation":
                result[name] = [r["id"] for r in prop.get("relation", [])]
            elif ptype == "rollup":
                rollup = prop.get("rollup", {})
                rtype = rollup.get("type", "")
                result[name] = rollup.get(rtype)
            else:
                # Fallback for unsupported types
                result[name] = str(prop)

        return result

    @staticmethod
    def build_property_value(prop_type: str, value: Any) -> dict:
        """Build a Notion property value from a simple value and known type."""
        if prop_type == "title":
            return {"title": [{"text": {"content": str(value)}}]}
        elif prop_type == "rich_text":
            return {"rich_text": [{"text": {"content": str(value)}}]}
        elif prop_type == "select":
            return {"select": {"name": str(value)}}
        elif prop_type == "multi_select":
            if isinstance(value, str):
                value = [v.strip() for v in value.split(",")]
            return {"multi_select": [{"name": v} for v in value]}
        elif prop_type == "status":
            return {"status": {"name": str(value)}}
        elif prop_type == "date":
            if isinstance(value, dict):
                return {"date": value}
            return {"date": {"start": str(value)}}
        elif prop_type == "checkbox":
            return {"checkbox": bool(value)}
        elif prop_type == "number":
            return {"number": float(value) if value is not None else None}
        elif prop_type == "url":
            return {"url": str(value) if value else None}
        elif prop_type == "email":
            return {"email": str(value) if value else None}
        else:
            raise ValueError(f"Unsupported property type: {prop_type}")


# Singleton
notion_client = NotionClient()
