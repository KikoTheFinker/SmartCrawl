import asyncio
from urllib.parse import urlparse

from playwright.async_api import async_playwright

from app.config.loaders.url_discovery_config_loader import get_crawler_config
from app.logging.logger import setup_logger
from app.url_discovery.utils.url_utils import normalize_base_url


class AsyncPlaywrightCrawler:
    def __init__(self, base_url: str):
        self.base_url = normalize_base_url(base_url)
        config = get_crawler_config()
        self.max_pages = config.max_pages
        self.concurrency = config.concurrency
        self.timeout = config.timeout
        self.load_state = config.load_state
        self.visited = set()
        self.to_visit = asyncio.Queue()
        self.queued = set()
        self.logger = setup_logger(__name__)

    async def crawl(self) -> list[str]:
        self.logger.info(f"Starting parallel Playwright crawl: {self.base_url}")

        await self.to_visit.put(self.base_url)
        self.queued.add(self.base_url)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()

            tasks = [asyncio.create_task(self._worker(context)) for _ in range(self.concurrency)]
            await asyncio.gather(*tasks)

            await context.close()
            await browser.close()

        self.logger.info(f"Total URLs crawled: {len(self.visited)}")
        return list(self.visited)

    async def _worker(self, context):
        while True:
            if len(self.visited) >= self.max_pages:
                return

            try:
                url = await asyncio.wait_for(self.to_visit.get(), timeout=5)
            except asyncio.TimeoutError:
                return

            if url in self.visited:
                self.to_visit.task_done()
                continue

            await self._visit_url(context, url)
            self.to_visit.task_done()

    async def _visit_url(self, context, url: str):
        page = await context.new_page()
        try:
            await page.goto(url, timeout=self.timeout)
            await page.wait_for_load_state(self.load_state)
            self.visited.add(url)
            self.logger.info(f"Visited: {url}")

            hrefs = await page.eval_on_selector_all(
                "a[href], [data-href]",
                "els => els.map(e => e.href || e.dataset.href)"
            )

            self.logger.debug(f"Found {len(hrefs)} links on {url}")

            for href in hrefs:
                if not href:
                    continue
                normalized = self._normalize_url(href)
                if (
                        self._is_same_domain(normalized)
                        and normalized not in self.visited
                        and normalized not in self.queued
                        and len(self.visited) + self.to_visit.qsize() < self.max_pages
                ):
                    await self.to_visit.put(normalized)
                    self.queued.add(normalized)
                    self.logger.debug(f"Queued: {normalized}")

        except Exception as e:
            self.logger.warning(f"Failed to load {url}: {e}")
        finally:
            await page.close()

    @staticmethod
    def _normalize_url(url: str) -> str:
        parsed = urlparse(url)
        return parsed._replace(fragment="", query="").geturl().rstrip("/")

    def _is_same_domain(self, url: str) -> bool:
        return urlparse(url).netloc == urlparse(self.base_url).netloc
