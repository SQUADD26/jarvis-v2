from crawl4ai import AsyncWebCrawler
from typing import Optional
from jarvis.utils.logging import get_logger

logger = get_logger(__name__)


class Crawl4AIClient:
    async def scrape_url(
        self,
        url: str,
        extract_markdown: bool = True
    ) -> dict:
        """Scrape a URL and return content."""
        async with AsyncWebCrawler(verbose=False) as crawler:
            result = await crawler.arun(url=url)

            return {
                "url": url,
                "title": result.metadata.get("title", "") if result.metadata else "",
                "content": result.markdown if extract_markdown else result.html,
                "success": result.success,
                "links": result.links.get("internal", [])[:10] if result.links else []
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
