import asyncio
from collections import Counter
from typing import Optional, Set
from urllib.parse import urlparse

import httpx

from app.crawlers.url_discovery.core.fetcher import HtmlFetcher
from app.crawlers.url_discovery.utils.html_content_processor import HtmlContentSaver
from app.crawlers.url_discovery.utils.html_parsing import extract_links, is_probably_html_url
from app.crawlers.url_discovery.utils.normalize import same_domain
from app.crawlers.url_discovery.utils.playwright_fetcher import PlaywrightHtmlFetcher
from app.utils.robots_cache import robots_cache


def _has_path_loop(url: str, min_window: int = 2, max_window: int = 4) -> bool:
    """Detect repeating segment patterns in a URL path.

    Returns True when the same sequence of consecutive path segments appears
    more than once, which is a strong signal of recursive navigation menus
    (e.g. ``/pocetna/za-kam/media-centar/pocetna/za-kam/media-centar/...``).
    """
    segments = [s for s in urlparse(url).path.split("/") if s]
    if len(segments) < min_window * 2:
        return False

    for window in range(min_window, min(max_window + 1, len(segments) // 2 + 1)):
        counts: Counter[tuple] = Counter()
        for i in range(len(segments) - window + 1):
            key = tuple(segments[i:i + window])
            counts[key] += 1
            if counts[key] >= 2:
                return True
    return False


class CrawlerWorker:
    def __init__(self, cfg, patterns, q: asyncio.PriorityQueue, seen: Set[str], found: Set[str],
                 sem: asyncio.Semaphore, root_netloc: str, logger, headers=None,
                 html_saver: Optional[HtmlContentSaver] = None,
                 playwright_fetcher: Optional[PlaywrightHtmlFetcher] = None):
        self.cfg = cfg
        self.patterns = patterns
        self.q = q
        self.seen = seen
        self.found = found
        self.sem = sem
        self.root_netloc = root_netloc
        self.logger = logger
        self.client = httpx.AsyncClient(headers=headers or {}, timeout=15.0, http2=True)
        self.html_saver = html_saver
        self.playwright_fetcher = playwright_fetcher

        self.fetcher = HtmlFetcher(self.client, patterns, logger)

    async def close(self):
        await self.client.aclose()
        if self.playwright_fetcher:
            await self.playwright_fetcher.close()

    async def _allowed(self, url: str) -> bool:
        if not same_domain(url, self.root_netloc, self.cfg.include_subdomains):
            if self.cfg.verbose:
                self.logger.info(f"Rejected (different domain): {url}")
            return False
        if not self.cfg.obey_robots:
            return True
        allowed = await robots_cache.allowed(url, self.client)
        if not allowed and self.cfg.verbose:
            self.logger.info(f"Rejected (robots.txt): {url}")
        return allowed

    async def run(self):
        max_depth = getattr(self.cfg, "max_depth", 15)

        while len(self.seen) < self.cfg.max_pages:
            try:
                try:
                    _, depth, url = await asyncio.wait_for(self.q.get(), timeout=10.0)
                except asyncio.TimeoutError:
                    if self.q.empty():
                        self.logger.info("Worker exiting: queue empty for 10s")
                        return
                    continue

                self.q.task_done()
                
                # Check if URL should be processed
                if url in self.seen:
                    self.logger.debug(f"Skipping (already seen): {url}")
                    continue

                if depth > max_depth:
                    self.logger.debug(f"Skipping (depth {depth} > max {max_depth}): {url}")
                    continue

                if _has_path_loop(url):
                    self.logger.debug(f"Skipping (path loop detected): {url}")
                    continue
                
                allowed = await self._allowed(url)
                if not allowed:
                    self.logger.info(f"Skipping (not allowed by robots.txt or domain): {url}")
                    continue
                
                if not is_probably_html_url(url, self.patterns):
                    self.logger.debug(f"Skipping (not HTML URL): {url}")
                    continue

                async with self.sem:
                    self.seen.add(url)
                    self.logger.info(f"Processing: {url}")
                    
                    # Use Playwright for JS rendering if configured, otherwise use httpx
                    if self.playwright_fetcher:
                        html = await self.playwright_fetcher.fetch_html(url, verbose=self.cfg.verbose)
                    else:
                        html = await self.fetcher.fetch_html(url, verbose=self.cfg.verbose)
                    
                    if not html:
                        self.logger.warning(f"Failed to fetch HTML (empty response): {url}")
                        continue

                    # Save HTML content if saver is configured
                    if self.html_saver:
                        try:
                            self.html_saver.save(url, html, self.logger)
                        except Exception as e:
                            self.logger.warning(f"Failed to save HTML for {url}: {e}")

                    links = extract_links(url, html,
                                          include_assets=self.cfg.include_assets,
                                          html_only=self.cfg.html_only,
                                          patterns=self.patterns)
                    self.logger.info(f"Found {len(links)} links on {url}")

                    await self._process_links(links, depth + 1)
            except Exception as e:
                self.logger.warning(f"Worker error: {e}")

    async def _process_links(self, links, child_depth: int):
        max_depth = getattr(self.cfg, "max_depth", 15)
        new_links, rejected_domain, rejected_html, already_seen, rejected_depth, rejected_loop = 0, 0, 0, 0, 0, 0

        for link in links:
            if not link or len(link) > self.patterns.max_url_length:
                continue

            if not await self._allowed(link):
                rejected_domain += 1
                continue

            if (not self.cfg.html_only) or is_probably_html_url(link, self.patterns):
                self.found.add(link)

            if (link not in self.seen) and is_probably_html_url(link, self.patterns):
                if child_depth > max_depth:
                    rejected_depth += 1
                elif _has_path_loop(link):
                    rejected_loop += 1
                else:
                    await self.q.put((10, child_depth, link))
                    new_links += 1
            else:
                if link in self.seen:
                    already_seen += 1
                else:
                    rejected_html += 1

        self.logger.info(
            f"Link processing: {new_links} added, {rejected_domain} rejected (domain), "
            f"{rejected_html} rejected (html), {already_seen} already seen"
            + (f", {rejected_depth} rejected (depth)" if rejected_depth else "")
            + (f", {rejected_loop} rejected (loop)" if rejected_loop else "")
        )
