from __future__ import annotations

from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig
from loguru import logger

from council.collectors.base import BaseCollector
from council.models.competitor import WebPage


class Crawl4AICollector(BaseCollector[WebPage]):
    def __init__(self, headless: bool = True, memory_saving: bool = True) -> None:
        self._browser_config = BrowserConfig(
            headless=headless, verbose=False, memory_saving_mode=memory_saving
        )
        self._crawler: AsyncWebCrawler | None = None

    async def start(self) -> None:
        if self._crawler is None:
            self._crawler = AsyncWebCrawler(config=self._browser_config)
            await self._crawler.start()

    async def close(self) -> None:
        if self._crawler:
            await self._crawler.close()
            self._crawler = None

    async def collect(self, query: str, max_results: int = 5) -> list[WebPage]:
        return await self.fetch_urls([query])

    async def fetch_one(self, url: str) -> WebPage:
        if self._crawler is None:
            await self.start()
        cfg = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            word_count_threshold=10,
            page_timeout=30000,
            exclude_external_links=True,
            remove_overlay_elements=True,
        )
        try:
            result = await self._crawler.arun(url=url, config=cfg)
            if not result.success:
                logger.warning("crawl_failed url={} error={}", url, result.error_message)
                return WebPage(url=url, success=False, error=result.error_message)
            md = result.markdown.raw_markdown if result.markdown else ""
            return WebPage(
                url=url,
                markdown=md,
                snippet=md[:500],
                success=True,
            )
        except Exception as exc:
            logger.error("crawl_error url={} error={}", url, exc)
            return WebPage(url=url, success=False, error=str(exc))

    async def fetch_urls(self, urls: list[str]) -> list[WebPage]:
        results: list[WebPage] = []
        for url in urls[:10]:
            page = await self.fetch_one(url)
            results.append(page)
        return results


async def collect_competitor_pages(domains: list[str]) -> list[WebPage]:
    collector = Crawl4AICollector()
    await collector.start()
    try:
        pages: list[WebPage] = []
        for domain in domains[:5]:
            url = domain if domain.startswith("http") else f"https://{domain}"
            page = await collector.fetch_one(url)
            pages.append(page)
        return pages
    finally:
        await collector.close()
