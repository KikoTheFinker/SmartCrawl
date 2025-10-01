import asyncio
from typing import List, Set, Tuple
from urllib.parse import urlparse

from app.crawlers.url_discovery.core.worker import CrawlerWorker
from app.crawlers.url_discovery.utils.patterns import ParsingPatterns


class BaseCrawler:
    """Core async crawler engine (internal use)."""

    def __init__(self, start_url: str, cfg, site_cfg, patterns: ParsingPatterns, logger):
        self.start_url = start_url.rstrip("/")
        self.cfg = cfg
        self.site_cfg = site_cfg
        self.patterns = patterns
        self.logger = logger

        self.seen: Set[str] = set()
        self.found: Set[str] = set()
        self.q: asyncio.PriorityQueue[Tuple[int, str]] = asyncio.PriorityQueue()
        self.sem = asyncio.Semaphore(max(1, self.cfg.concurrency))

        self.worker = CrawlerWorker(
            cfg=self.cfg,
            patterns=self.patterns,
            q=self.q,
            seen=self.seen,
            found=self.found,
            sem=self.sem,
            root_netloc=urlparse(self.start_url).netloc,
            logger=self.logger,
            headers=self.site_cfg.headers,
        )

    async def __aenter__(self):
        """Allow use in async with."""
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """Ensure resources are cleaned up."""
        await self.close()

    async def run(self) -> List[str]:
        self.logger.info("Starting crawl")
        await self.q.put((0, self.start_url))
        workers = [asyncio.create_task(self.worker.run()) for _ in range(self.cfg.concurrency)]
        try:
            await self.q.join()
            await asyncio.gather(*workers, return_exceptions=True)
        finally:
            for w in workers:
                if not w.done():
                    w.cancel()

        self.logger.info(f"Crawler finished. Seen: {len(self.seen)}, Found: {len(self.found)}")
        return sorted(self.found)

    async def close(self) -> None:
        await self.worker.close()
