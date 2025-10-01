import asyncio
from typing import Set

import httpx

from app.crawlers.url_discovery.core.fetcher import HtmlFetcher
from app.crawlers.url_discovery.utils.html_parsing import extract_links, is_probably_html_url
from app.crawlers.url_discovery.utils.normalize import same_domain
from app.utils.robots_cache import robots_cache


class CrawlerWorker:
    def __init__(self, cfg, patterns, q: asyncio.PriorityQueue, seen: Set[str], found: Set[str],
                 sem: asyncio.Semaphore, root_netloc: str, logger, headers=None):
        self.cfg = cfg
        self.patterns = patterns
        self.q = q
        self.seen = seen
        self.found = found
        self.sem = sem
        self.root_netloc = root_netloc
        self.logger = logger
        self.client = httpx.AsyncClient(headers=headers or {}, timeout=15.0, http2=True)

        self.fetcher = HtmlFetcher(self.client, patterns, logger)

    async def close(self):
        await self.client.aclose()

    async def _allowed(self, url: str) -> bool:
        if not same_domain(url, self.root_netloc, self.cfg.include_subdomains):
            if self.cfg.verbose:
                self.logger.info(f"Rejected (different domain): {url}")
            return False
        if not self.cfg.obey_robots:
            return True
        return await robots_cache.allowed(url, self.client)

    async def run(self):
        while len(self.seen) < self.cfg.max_pages:
            try:
                try:
                    _, url = await asyncio.wait_for(self.q.get(), timeout=10.0)
                except asyncio.TimeoutError:
                    if self.q.empty():
                        self.logger.info("Worker exiting: queue empty for 10s")
                        return
                    continue

                self.q.task_done()
                if url in self.seen or not await self._allowed(url) or not is_probably_html_url(url, self.patterns):
                    continue

                async with self.sem:
                    self.seen.add(url)
                    html = await self.fetcher.fetch_html(url, verbose=self.cfg.verbose)
                    if not html:
                        continue

                    links = extract_links(url, html,
                                          include_assets=self.cfg.include_assets,
                                          html_only=self.cfg.html_only,
                                          patterns=self.patterns)
                    self.logger.info(f"Found {len(links)} links on {url}")

                    await self._process_links(links)
            except Exception as e:
                self.logger.warning(f"Worker error: {e}")

    async def _process_links(self, links):
        new_links, rejected_domain, rejected_html, already_seen = 0, 0, 0, 0
        for link in links:
            if not link or len(link) > self.patterns.max_url_length:
                continue

            if not await self._allowed(link):
                rejected_domain += 1
                continue

            if (not self.cfg.html_only) or is_probably_html_url(link, self.patterns):
                self.found.add(link)

            if (link not in self.seen) and is_probably_html_url(link, self.patterns):
                await self.q.put((10, link))
                new_links += 1
            else:
                if link in self.seen:
                    already_seen += 1
                else:
                    rejected_html += 1

        self.logger.info(
            f"Link processing: {new_links} added, {rejected_domain} rejected (domain), "
            f"{rejected_html} rejected (html), {already_seen} already seen"
        )
