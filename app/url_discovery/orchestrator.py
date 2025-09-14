from typing import List

from app.config.loaders.url_discovery_config_loader import get_postprocess_config
from app.logging.logger import setup_logger
from app.url_discovery.core.patterns import load_patterns
from app.url_discovery.core.postprocess import collapse_language_variants
from app.url_discovery.http_async_crawler import HttpAsyncCrawler
from app.url_discovery.sitemap_discoverer import SitemapDiscoverer
from app.url_discovery.utils.url_utils import normalize_base_url


class UrlDiscoveryOrchestrator:
    def __init__(self, base_url: str):
        self.base_url = normalize_base_url(base_url)
        self.logger = setup_logger(__name__)
        self.post_cfg = get_postprocess_config()
        self.patterns = load_patterns()

    async def discover(self) -> List[str]:
        site = SitemapDiscoverer(self.base_url)
        try:
            urls = await site.discover_urls()
        except Exception as e:
            self.logger.warning(f"Sitemap discover failed: {e}")
            urls = []

        if not urls:
            self.logger.info("No URLs from sitemap; falling back to HTTP crawler")
            crawler = HttpAsyncCrawler(self.base_url)
            try:
                urls = await crawler.run()
                self.logger.info(f"HTTP crawler found {len(urls)} URLs")
            finally:
                await crawler.close()

        urls = [u for u in urls if isinstance(u, str) and u.startswith(("http://", "https://"))]
        return self._postprocess(urls)

    def _postprocess(self, links: List[str]) -> List[str]:
        unique = sorted(set(links))
        if self.post_cfg.collapse_language_variants:
            defaults = [""] + [l.strip().lower() for l in self.post_cfg.default_languages if l.strip()]
            unique = collapse_language_variants(unique, defaults, self.patterns)
        return unique
