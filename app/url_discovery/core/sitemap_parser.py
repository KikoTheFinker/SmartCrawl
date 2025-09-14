from typing import List
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.logging.logger import setup_logger
from app.url_discovery.utils.compression_utils import maybe_decompress


class SitemapParser:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.logger = setup_logger(__name__)

    async def parse_sitemap_urls(self, sitemap_url: str) -> List[str]:
        self.logger.info(f"Parsing sitemap: {sitemap_url}")
        try:
            response = await self.client.get(sitemap_url)
            response.raise_for_status()
            content = maybe_decompress(sitemap_url, response.content)
        except httpx.RequestError as e:
            self.logger.warning(f"Fetch failed for {sitemap_url}: {e}")
            return []
        except Exception as e:
            self.logger.warning(f"Error retrieving sitemap content from {sitemap_url}: {e}")
            return []

        soup = BeautifulSoup(content, "xml")
        if soup.find("urlset"):
            return [self._normalize_url(loc.text.strip()) for loc in soup.find_all("loc")]
        else:
            return []

    async def get_nested_sitemaps(self, sitemap_url: str) -> List[str]:
        try:
            response = await self.client.get(sitemap_url)
            response.raise_for_status()
            content = maybe_decompress(sitemap_url, response.content)
        except Exception:
            return []

        soup = BeautifulSoup(content, "xml")
        if soup.find("sitemapindex"):
            return [loc.text.strip() for loc in soup.find_all("loc")]
        return []

    @staticmethod
    def _normalize_url(url: str) -> str:
        parsed = urlparse(url)
        return parsed._replace(fragment="", query="").geturl().rstrip("/")
