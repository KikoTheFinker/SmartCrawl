import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from requests import RequestException

from app.config.loaders.url_discovery_config_loader import get_sitemap_config
from app.exceptions import SitemapDiscoveryError
from app.logging.logger import setup_logger
from app.url_discovery.utils.compression_utils import maybe_decompress
from app.url_discovery.utils.url_utils import normalize_base_url


class SitemapDiscoverer:
    SITEMAP_PATTERN = re.compile(r"(?i)^sitemap:\s*(.+)$")

    def __init__(self, base_url: str):
        self.base_url = normalize_base_url(base_url)
        self.config = get_sitemap_config()
        self.logger = setup_logger(__name__)

    def discover_urls(self) -> list[str]:
        self.logger.info(f"Discovering sitemap URLs for: {self.base_url}")
        try:
            sitemap_urls = self._try_fetch_sitemap_urls()
        except Exception as e:
            self.logger.warning(f"Sitemap discovery failed: {e}")
            sitemap_urls = []

        all_urls = set()
        for sitemap_url in sitemap_urls:
            all_urls.update(self._parse_sitemap(sitemap_url))

        self.logger.info(f"Total discovered URLs: {len(all_urls)}")
        return sorted(all_urls)

    def _try_fetch_sitemap_urls(self) -> list[str]:
        for attempt in range(self.config.retry):
            try:
                return self._get_sitemap_urls_from_robots()
            except SitemapDiscoveryError as e:
                self.logger.warning(f"Attempt {attempt + 1}: {e}")
        return self._try_common_sitemap_urls()

    def _get_sitemap_urls_from_robots(self) -> list[str]:
        robots_url = urljoin(self.base_url, "/robots.txt")
        try:
            response = requests.get(robots_url, timeout=self.config.timeout, headers=self.config.headers)
            response.raise_for_status()
        except RequestException as e:
            raise SitemapDiscoveryError(f"Failed to fetch robots.txt: {e}")

        try:
            content = maybe_decompress(robots_url, response.content)
            text = content.decode("utf-8")
        except Exception as e:
            raise SitemapDiscoveryError(f"Decompression or decoding failed: {e}")

        return self._extract_sitemap_urls(text)

    def _extract_sitemap_urls(self, robots_txt: str) -> list[str]:
        return [
            match.group(1).strip()
            for line in robots_txt.splitlines()
            if (match := self.SITEMAP_PATTERN.match(line.strip()))
        ]

    def _try_common_sitemap_urls(self) -> list[str]:
        found = []
        for path in self.config.common_paths:
            url = urljoin(self.base_url, path)
            self.logger.info(f"Trying common sitemap path: {url}")
            try:
                response = requests.get(url, timeout=self.config.timeout, headers=self.config.headers)
                response.raise_for_status()
                content = maybe_decompress(url, response.content)
                soup = BeautifulSoup(content, "xml")
                if soup.find("urlset") or soup.find("sitemapindex"):
                    found.append(url)
            except Exception as e:
                self.logger.warning(f"Failed to parse sitemap at {url}: {e}")
        return found

    def _parse_sitemap(self, sitemap_url: str) -> list[str]:
        self.logger.info(f"Parsing sitemap: {sitemap_url}")
        try:
            response = requests.get(sitemap_url, timeout=self.config.timeout, headers=self.config.headers)
            response.raise_for_status()
            content = maybe_decompress(sitemap_url, response.content)
        except RequestException as e:
            self.logger.warning(f"Fetch failed for {sitemap_url}: {e}")
            return []
        except Exception as e:
            self.logger.warning(f"Error retrieving sitemap content from {sitemap_url}: {e}")
            return []

        soup = BeautifulSoup(content, "xml")
        if soup.find("sitemapindex"):
            nested = [loc.text.strip() for loc in soup.find_all("loc")]
            all_nested = []
            for sub_url in nested:
                all_nested.extend(self._parse_sitemap(sub_url))
            return all_nested
        elif soup.find("urlset"):
            return [self._normalize_url(loc.text.strip()) for loc in soup.find_all("loc")]
        else:
            self.logger.warning(f"Unknown sitemap format at {sitemap_url}")
            return []

    @staticmethod
    def _normalize_url(url: str) -> str:
        parsed = urlparse(url)
        return parsed._replace(fragment="", query="").geturl().rstrip("/")
