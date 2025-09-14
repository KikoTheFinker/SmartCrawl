import asyncio
import re
from typing import List, Set
from urllib.parse import urljoin, urlparse

import httpx

from app.config.loaders.url_discovery_config_loader import get_sitemap_config
from app.exceptions import SitemapDiscoveryError
from app.logging.logger import setup_logger
from app.url_discovery.core.async_worker_pool import QueueProcessor
from app.url_discovery.core.sitemap_parser import SitemapParser
from app.url_discovery.utils.compression_utils import maybe_decompress
from app.url_discovery.utils.url_utils import normalize_base_url


class SitemapUrlCollector:
    def __init__(self, parser: SitemapParser, config):
        self.parser = parser
        self.config = config
        self.logger = setup_logger(__name__)

    async def collect_urls_from_sitemap(self, sitemap_url: str) -> Set[str]:
        self.logger.info(f"Collecting URLs from sitemap: {sitemap_url}")
        try:
            urls = await self.parser.parse_sitemap_urls(sitemap_url)
            url_set = set(urls)

            if len(url_set) > self.config.max_urls_per_sitemap:
                self.logger.warning(
                    f"Sitemap {sitemap_url} has {len(url_set)} URLs, limiting to {self.config.max_urls_per_sitemap}")
                url_set = set(list(url_set)[:self.config.max_urls_per_sitemap])

            return url_set
        except Exception as e:
            self.logger.error(f"Failed to collect URLs from {sitemap_url}: {e}")
            return set()


class SitemapUrlDiscoverer:
    SITEMAP_PATTERN = re.compile(r"(?i)^sitemap:\s*(.+)$")

    def __init__(self, client: httpx.AsyncClient, config):
        self.client = client
        self.config = config
        self.logger = setup_logger(__name__)

    async def discover_sitemap_urls(self, base_url: str) -> List[str]:
        self.logger.info(f"Discovering sitemap URLs for: {base_url}")

        for attempt in range(self.config.retry):
            try:
                sitemap_urls = await self._get_sitemap_urls_from_robots(base_url)
                if sitemap_urls:
                    return sitemap_urls
            except SitemapDiscoveryError as e:
                self.logger.warning(f"Attempt {attempt + 1}: {e}")

        return await self._try_common_sitemap_urls(base_url)

    async def _get_sitemap_urls_from_robots(self, base_url: str) -> List[str]:
        robots_url = urljoin(base_url, "/robots.txt")
        try:
            resp = await self.client.get(robots_url)
            resp.raise_for_status()
        except httpx.RequestError as e:
            raise SitemapDiscoveryError(f"Failed to fetch robots.txt: {e}")

        final_url = str(resp.url)
        if final_url != robots_url:
            p = urlparse(final_url)
            base_url = f"{p.scheme}://{p.netloc}"
            self.logger.info(f"Base URL changed via redirect: {robots_url} → {final_url} (base={base_url})")

        try:
            content = maybe_decompress(final_url, resp.content)
            text = content.decode("utf-8", errors="replace")
        except Exception as e:
            raise SitemapDiscoveryError(f"Decompression or decoding failed: {e}")

        return self._extract_sitemap_urls(text, base_url)

    def _extract_sitemap_urls(self, robots_txt: str, base_url: str) -> List[str]:
        sitemap_urls = []
        for line in robots_txt.splitlines():
            if match := self.SITEMAP_PATTERN.match(line.strip()):
                sitemap_url = match.group(1).strip()
                if not sitemap_url.startswith(('http://', 'https://')):
                    sitemap_url = urljoin(base_url, sitemap_url)
                sitemap_urls.append(sitemap_url)
        return sitemap_urls

    async def _try_common_sitemap_urls(self, base_url: str) -> List[str]:
        tasks = []
        for path in self.config.common_paths:
            url = urljoin(base_url, path)
            tasks.append(self._check_common_sitemap_url(url))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        found = []
        for result in results:
            if isinstance(result, str):
                found.append(result)
            elif isinstance(result, Exception):
                self.logger.warning(f"Failed to check common sitemap: {result}")
        return found

    async def _check_common_sitemap_url(self, url: str) -> str | None:
        self.logger.info(f"Trying common sitemap path: {url}")
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            content = maybe_decompress(url, response.content)
            soup = __import__('bs4').BeautifulSoup(content, "xml")
            if soup.find("urlset") or soup.find("sitemapindex"):
                return url
        except Exception as e:
            self.logger.warning(f"Failed to parse sitemap at {url}: {e}")
        return None


class SitemapDiscoveryProcessor(QueueProcessor[str, str]):
    def __init__(self, base_url: str):
        self.base_url = normalize_base_url(base_url)
        self.config = get_sitemap_config()
        self.logger = setup_logger(__name__)

        self.client = httpx.AsyncClient(
            headers=self.config.headers,
            timeout=self.config.timeout,
            http2=True,
            follow_redirects=True,
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=25)
        )
        self.parser = SitemapParser(self.client)
        self.url_collector = SitemapUrlCollector(self.parser, self.config)
        self.url_discoverer = SitemapUrlDiscoverer(self.client, self.config)

        super().__init__(self.config.concurrency, self.config.worker_timeout)

    async def discover_urls(self) -> List[str]:
        try:
            sitemap_urls = await self.url_discoverer.discover_sitemap_urls(self.base_url)
        except Exception as e:
            self.logger.warning(f"Sitemap discovery failed: {e}")
            sitemap_urls = []

        if not sitemap_urls:
            self.logger.warning("No sitemap URLs found")
            return []

        all_urls = await self.process_with_queue(sitemap_urls)

        if len(all_urls) > self.config.max_total_urls:
            self.logger.warning(
                f"Total URLs ({len(all_urls)}) exceeds limit ({self.config.max_total_urls}), truncating")
            all_urls = set(list(all_urls)[:self.config.max_total_urls])

        self.logger.info(f"Total discovered URLs: {len(all_urls)}")
        return sorted(all_urls)

    async def process_item(self, sitemap_url: str) -> Set[str]:
        return await self.url_collector.collect_urls_from_sitemap(sitemap_url)

    async def get_next_items(self, sitemap_url: str) -> List[str]:
        return await self.parser.get_nested_sitemaps(sitemap_url)

    async def close(self):
        await self.client.aclose()
