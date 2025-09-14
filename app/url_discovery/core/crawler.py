import asyncio
from typing import Optional, Set, Tuple, List
from urllib.parse import urlparse, parse_qsl

import httpx

from app.config.loaders.url_discovery_config_loader import get_crawler_config, get_sitemap_config
from app.logging.logger import setup_logger
from app.url_discovery.core.html_parsing import extract_links, is_probably_html_url
from app.url_discovery.core.normalize import normalize_link, canonical_netloc, same_domain
from app.url_discovery.core.patterns import load_patterns, ParsingPatterns


class HttpAsyncCrawler:
    def __init__(self, start_url: str):
        self.logger = setup_logger(__name__)
        self.cfg = get_crawler_config()
        self.site_cfg = get_sitemap_config()
        self.patterns: ParsingPatterns = load_patterns()

        self.start_url = (normalize_link(start_url, "", self.patterns) or start_url).rstrip("/")
        root = urlparse(self.start_url)
        _, nl = canonical_netloc(root.scheme or "https", root.netloc, self.patterns.strip_www,
                                 self.patterns.prefer_https)
        self.root_netloc = nl
        self.logger.info(f"Crawler initialized: start_url={self.start_url}, root_netloc={self.root_netloc}")

        self.seen: Set[str] = set()
        self.found: Set[str] = set()
        self.q: asyncio.PriorityQueue[Tuple[int, str]] = asyncio.PriorityQueue()
        self.sem = asyncio.Semaphore(max(1, self.cfg.concurrency))

        headers = dict(self.site_cfg.headers or {})
        self.client = httpx.AsyncClient(
            headers=headers,
            timeout=15.0,
            http2=True,
            limits=httpx.Limits(
                max_connections=max(64, self.cfg.concurrency * 4),
                max_keepalive_connections=max(32, self.cfg.concurrency * 2)
            ),
        )

    async def close(self):
        await self.client.aclose()

    def _prio_for(self, url: str) -> int:
        p = urlparse(url)
        path = p.path or "/"
        score = 5 if path in ("", "/") else 10 + min(50, path.count("/") * 5)
        q = {k.lower() for k, _ in parse_qsl(p.query)}
        if q & self.patterns.pagination_hints:
            score += 20
        return score

    def _allowed(self, url: str) -> bool:
        if not same_domain(url, self.root_netloc, self.cfg.include_subdomains):
            if self.cfg.verbose:
                self.logger.info(f"URL rejected (different domain): {url} (root: {self.root_netloc})")
            return False
        if not self.cfg.obey_robots:
            return True
        return True

    async def _fetch_html(self, url: str) -> Optional[str]:
        try:
            if self.cfg.verbose:
                self.logger.info(f"GET {url}")
            r = await self.client.get(url, follow_redirects=True)
            ctype = r.headers.get("content-type", "") or ""
            if self.cfg.verbose:
                self.logger.info(f"{r.status_code} {url} [{ctype}]")
            if self.patterns.html_ct.search(ctype):
                return r.text
            return None
        except Exception as e:
            if self.cfg.verbose:
                self.logger.warning(f"HTTP error at {url}: {e}")
            return None

    async def _prepare(self):
        await self.q.put((self._prio_for(self.start_url), self.start_url))
        if (not self.cfg.html_only) or is_probably_html_url(self.start_url, self.patterns):
            self.found.add(self.start_url)

    async def _worker(self):
        while len(self.seen) < self.cfg.max_pages:
            try:
                try:
                    _, url = await asyncio.wait_for(self.q.get(), timeout=10.0)
                except asyncio.TimeoutError:
                    if self.q.empty():
                        self.logger.info("Worker exiting: queue empty for 10 seconds")
                        return
                    continue

                self.q.task_done()

                if url in self.seen:
                    continue
                if not self._allowed(url):
                    continue
                if not is_probably_html_url(url, self.patterns):
                    continue

                async with self.sem:
                    self.seen.add(url)
                    try:
                        html = await self._fetch_html(url)
                        if html:
                            links = extract_links(url, html, include_assets=self.cfg.include_assets,
                                                  html_only=self.cfg.html_only, patterns=self.patterns)
                            self.logger.info(f"Found {len(links)} links on {url}")

                            new_links_added = 0
                            rejected_domain = 0
                            rejected_html = 0
                            already_seen = 0

                            for link in links:
                                if not link or len(link) > self.patterns.max_url_length:
                                    continue

                                if not self._allowed(link):
                                    rejected_domain += 1
                                    continue

                                if (not self.cfg.html_only) or is_probably_html_url(link, self.patterns):
                                    self.found.add(link)

                                if (link not in self.seen) and is_probably_html_url(link, self.patterns):
                                    await self.q.put((self._prio_for(link), link))
                                    new_links_added += 1
                                else:
                                    if link in self.seen:
                                        already_seen += 1
                                    else:
                                        rejected_html += 1

                            self.logger.info(
                                f"Link processing: {new_links_added} added, {rejected_domain} rejected (domain), {rejected_html} rejected (html), {already_seen} already seen")
                    except Exception as e:
                        self.logger.warning(f"Error processing {url}: {e}")
            except Exception as e:
                self.logger.warning(f"Worker error: {e}")

    async def run(self) -> List[str]:
        await self._prepare()
        self.logger.info(f"Starting crawler with {self.cfg.concurrency} workers, max_pages: {self.cfg.max_pages}")
        workers = [asyncio.create_task(self._worker()) for _ in range(self.cfg.concurrency)]

        try:
            await self.q.join()

            await asyncio.gather(*workers, return_exceptions=True)

        except Exception as e:
            self.logger.warning(f"Error during crawling: {e}")
        finally:
            for w in workers:
                if not w.done():
                    w.cancel()

        self.logger.info(f"Crawler finished. Seen: {len(self.seen)}, Found: {len(self.found)}")
        return sorted(self.found)
