"""Crawl4AI REST API client."""

import httpx
from typing import Optional
from jarvis.config import get_settings
from jarvis.utils.logging import get_logger

logger = get_logger(__name__)


class Crawl4AIClient:
    """Client for Crawl4AI REST API service."""

    def __init__(self, base_url: str = None, timeout: float = 60.0):
        settings = get_settings()
        self.base_url = (base_url or settings.crawl4ai_url).rstrip("/")
        self.timeout = timeout

    async def health_check(self) -> bool:
        """Check if Crawl4AI service is healthy."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.base_url}/health")
                return resp.status_code == 200
        except Exception as e:
            logger.error(f"Crawl4AI health check failed: {e}")
            return False

    async def scrape_url(
        self,
        url: str,
        extract_markdown: bool = True,
        max_depth: int = 1,
        max_pages: int = 1
    ) -> dict:
        """
        Scrape a URL using Crawl4AI service.

        Args:
            url: URL to scrape
            extract_markdown: If True, return markdown; otherwise raw HTML
            max_depth: Maximum depth of links to follow
            max_pages: Maximum number of pages to process

        Returns:
            dict with url, title, content, success, links
        """
        payload = {
            "urls": [url],
            "crawler_config": {
                "max_depth": max_depth,
                "max_pages": max_pages
            },
            "extract_config": {
                "mode": "markdown" if extract_markdown else "raw_html"
            }
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/crawl",
                    json=payload
                )
                resp.raise_for_status()
                data = resp.json()

            # Parse response - Crawl4AI returns results per URL
            if isinstance(data, dict) and "results" in data:
                results = data["results"]
            elif isinstance(data, list):
                results = data
            else:
                results = [data]

            if not results:
                return {
                    "url": url,
                    "title": "",
                    "content": "",
                    "success": False,
                    "links": []
                }

            result = results[0] if results else {}

            return {
                "url": url,
                "title": result.get("metadata", {}).get("title", "") or result.get("title", ""),
                "content": result.get("markdown", "") or result.get("content", ""),
                "success": result.get("success", True),
                "links": result.get("links", {}).get("internal", [])[:10] if isinstance(result.get("links"), dict) else []
            }

        except httpx.HTTPStatusError as e:
            logger.error(f"Crawl4AI HTTP error: {e.response.status_code} - {e.response.text[:200]}")
            return {
                "url": url,
                "title": "",
                "content": "",
                "success": False,
                "links": []
            }
        except Exception as e:
            logger.error(f"Crawl4AI scrape failed: {e}")
            return {
                "url": url,
                "title": "",
                "content": "",
                "success": False,
                "links": []
            }

    async def scrape_and_extract(
        self,
        url: str,
        prompt: str = "Estrai e riassumi i punti chiave di questa pagina."
    ) -> dict:
        """Scrape URL and return content for extraction."""
        result = await self.scrape_url(url)

        if not result["success"]:
            return {
                "url": url,
                "extracted_content": None,
                "success": False
            }

        return {
            "url": url,
            "content": result["content"],
            "title": result["title"],
            "success": True
        }


# Singleton
crawler = Crawl4AIClient()
