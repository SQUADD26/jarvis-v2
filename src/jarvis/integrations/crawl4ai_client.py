"""Crawl4AI REST API client with manual deep crawling support."""

import asyncio
import httpx
from typing import Optional
from urllib.parse import urljoin, urlparse
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
                "max_pages": max_pages,
                "wait_until": "networkidle",  # Wait for all network requests
                "page_timeout": 60000,  # 60 seconds for JS rendering
                "wait_for": "css:article",  # Wait for article element (Docusaurus)
                "wait_for_timeout": 30000  # 30s timeout for wait_for
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

    async def deep_crawl(
        self,
        url: str,
        max_depth: int = DEFAULT_MAX_DEPTH,
        max_pages: int = DEFAULT_MAX_PAGES,
        include_external: bool = False,
        delay_between_requests: float = 0.05,  # Configurable delay (50ms default)
        concurrent_requests: int = 3  # Number of concurrent scrapes
    ) -> dict:
        """
        Deep crawl a URL following internal links recursively (BFS strategy).

        Args:
            url: Starting URL to crawl
            max_depth: Maximum depth of links to follow (0 = only starting page)
            max_pages: Maximum total pages to crawl
            include_external: Whether to follow external links

        Returns:
            dict with pages (list of page results), total_pages, success
        """
        # Parse base domain for internal link filtering
        parsed_base = urlparse(url)
        base_domain = parsed_base.netloc

        # Track visited URLs and pages to crawl
        visited: set[str] = set()
        pages: list[dict] = []
        semaphore = asyncio.Semaphore(concurrent_requests)

        # Queue: (url, depth)
        queue: list[tuple[str, int]] = [(url, 0)]

        logger.info(f"Starting deep crawl of {url} (max_depth={max_depth}, max_pages={max_pages}, concurrent={concurrent_requests})")

        async def scrape_with_semaphore(target_url: str, depth: int) -> dict | None:
            """Scrape a single URL with semaphore-controlled concurrency."""
            async with semaphore:
                if delay_between_requests > 0:
                    await asyncio.sleep(delay_between_requests)
                result = await self._scrape_single_page(target_url)
                if result["success"]:
                    return {
                        "url": target_url,
                        "title": result["title"],
                        "content": result["content"],
                        "depth": depth,
                        "links": result.get("links", [])
                    }
                return None

        # Process in waves - BFS with concurrent scraping per depth level
        while queue and len(pages) < max_pages:
            # Take a batch of URLs to process concurrently
            batch_size = min(concurrent_requests * 2, max_pages - len(pages), len(queue))
            batch = []

            for _ in range(batch_size):
                if not queue:
                    break
                current_url, depth = queue.pop(0)
                normalized_url = self._normalize_url(current_url)
                if normalized_url not in visited:
                    visited.add(normalized_url)
                    batch.append((current_url, depth))

            if not batch:
                break

            # Scrape batch concurrently
            tasks = [scrape_with_semaphore(u, d) for u, d in batch]
            results = await asyncio.gather(*tasks)

            # Process results
            for result in results:
                if result and len(pages) < max_pages:
                    pages.append({
                        "url": result["url"],
                        "title": result["title"],
                        "content": result["content"],
                        "depth": result["depth"]
                    })
                    logger.info(f"Crawled page {len(pages)}/{max_pages}: {result['title'][:50] if result['title'] else result['url']}")

                    # Add links to queue if we haven't reached max depth
                    if result["depth"] < max_depth:
                        for link in result.get("links", []):
                            link_url = link.get("href", "") if isinstance(link, dict) else str(link)
                            if not link_url:
                                continue

                            # Resolve relative URLs
                            absolute_url = urljoin(result["url"], link_url)
                            parsed_link = urlparse(absolute_url)

                            # Filter: only http/https
                            if parsed_link.scheme not in ("http", "https"):
                                continue

                            # Filter: internal links only (unless include_external)
                            if not include_external and parsed_link.netloc != base_domain:
                                continue

                            # Skip already visited
                            if self._normalize_url(absolute_url) in visited:
                                continue

                            # Skip common non-content URLs
                            if self._should_skip_url(absolute_url):
                                continue

                            queue.append((absolute_url, result["depth"] + 1))

        logger.info(f"Deep crawl completed: {len(pages)} pages crawled")

        return {
            "start_url": url,
            "pages": pages,
            "total_pages": len(pages),
            "success": len(pages) > 0
        }

    async def _scrape_single_page(self, url: str) -> dict:
        """Scrape a single page without following links."""
        payload = {
            "urls": [url],
            "crawler_config": {
                "wait_until": "networkidle",  # Wait for all network requests
                "page_timeout": 60000,  # 60 seconds for JS rendering
                "wait_for": "css:article",  # Wait for article element (Docusaurus)
                "wait_for_timeout": 30000  # 30s timeout for wait_for
            },
            "extract_config": {
                "mode": "markdown"
            }
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:  # Shorter timeout for single pages
                resp = await client.post(
                    f"{self.base_url}/crawl",
                    json=payload
                )
                resp.raise_for_status()
                data = resp.json()

            # Parse response
            if isinstance(data, dict) and "results" in data:
                results = data["results"]
            elif isinstance(data, list):
                results = data
            else:
                results = [data]

            if not results:
                return {"success": False, "content": "", "title": "", "links": []}

            result = results[0]

            # Extract markdown
            markdown_data = result.get("markdown", {})
            if isinstance(markdown_data, dict):
                content = markdown_data.get("raw_markdown", "") or markdown_data.get("fit_markdown", "")
            else:
                content = markdown_data or ""

            # Extract links
            links_data = result.get("links", {})
            if isinstance(links_data, dict):
                links = links_data.get("internal", [])
            else:
                links = []

            return {
                "success": result.get("success", True),
                "content": content,
                "title": result.get("metadata", {}).get("title", "") or result.get("title", ""),
                "links": links
            }

        except Exception as e:
            logger.warning(f"Failed to scrape {url}: {e}")
            return {"success": False, "content": "", "title": "", "links": []}

    def _normalize_url(self, url: str) -> str:
        """Normalize URL for comparison (remove trailing slash, fragments)."""
        parsed = urlparse(url)
        # Remove fragment, normalize path
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"
        if parsed.query:
            normalized += f"?{parsed.query}"
        return normalized.lower()

    def _should_skip_url(self, url: str) -> bool:
        """Check if URL should be skipped (non-content pages)."""
        skip_patterns = [
            "/login", "/logout", "/signin", "/signout", "/signup",
            "/auth/", "/oauth/", "/api/", "/admin/",
            ".pdf", ".zip", ".tar", ".gz", ".exe", ".dmg",
            ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
            ".css", ".js", ".json", ".xml",
            "/cdn-cgi/", "/wp-admin/", "/wp-login",
            "#", "javascript:", "mailto:", "tel:"
        ]
        url_lower = url.lower()
        return any(pattern in url_lower for pattern in skip_patterns)


# Singleton
crawler = Crawl4AIClient()
