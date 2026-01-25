"""Crawl4AI REST API client."""

import httpx
from typing import Optional
from jarvis.config import get_settings
from jarvis.utils.logging import get_logger

logger = get_logger(__name__)


class Crawl4AIClient:
    """Client for Crawl4AI REST API service."""

    # Default settings
    DEFAULT_TIMEOUT = 3600.0  # 1 hour for long documentation
    DEFAULT_MAX_DEPTH = 3
    DEFAULT_MAX_PAGES = 1000

    def __init__(self, base_url: str = None, timeout: float = DEFAULT_TIMEOUT):
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
        max_depth: int = DEFAULT_MAX_DEPTH,
        max_pages: int = DEFAULT_MAX_PAGES
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

            # Extract markdown content - Crawl4AI returns markdown as a dict
            markdown_data = result.get("markdown", {})
            if isinstance(markdown_data, dict):
                content = markdown_data.get("raw_markdown", "") or markdown_data.get("fit_markdown", "")
            else:
                content = markdown_data or ""

            # Extract links
            links_data = result.get("links", {})
            if isinstance(links_data, dict):
                links = links_data.get("internal", [])[:10]
            else:
                links = []

            return {
                "url": url,
                "title": result.get("metadata", {}).get("title", "") or result.get("title", ""),
                "content": content,
                "success": result.get("success", True),
                "links": links
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
