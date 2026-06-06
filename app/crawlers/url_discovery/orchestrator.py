from typing import List, Optional

from app.config.loaders.url_discovery_config_loader import get_postprocess_config
from app.config.models.app_config_model import HtmlSavingConfig
from app.crawlers.url_discovery.http_async_crawler import HttpAsyncCrawler
from app.crawlers.url_discovery.sitemap_discoverer import SitemapDiscoverer
from app.crawlers.url_discovery.utils.html_content_processor import HtmlContentSaver
from app.crawlers.url_discovery.utils.patterns import load_patterns
from app.crawlers.url_discovery.utils.playwright_fetcher import PlaywrightHtmlFetcher
from app.crawlers.url_discovery.utils.postprocess import collapse_language_variants
from app.logging.logger import setup_logger
from app.utils.url_utils import normalize_base_url


class UrlDiscoveryOrchestrator:
    def __init__(self, base_url: str, use_sitemap: bool = True,
                 html_saving_config: Optional[HtmlSavingConfig] = None):
        self.base_url = normalize_base_url(base_url)
        self.logger = setup_logger(__name__)
        self.post_cfg = get_postprocess_config()
        self.patterns = load_patterns()
        self.use_sitemap = use_sitemap
        self.html_saving_config = html_saving_config
        
        # Create HTML saver if enabled
        self.html_saver: Optional[HtmlContentSaver] = None
        self.playwright_fetcher: Optional[PlaywrightHtmlFetcher] = None
        
        # Store playwright concurrency for later use
        self.playwright_concurrency = 4  # Default
        
        if html_saving_config and html_saving_config.enabled:
            self.html_saver = HtmlContentSaver(
                output_dir=html_saving_config.output_dir,
                save_raw=html_saving_config.save_raw,
                save_processed=html_saving_config.save_processed,
                output_format=html_saving_config.output_format,
                include_tables=html_saving_config.include_tables,
                include_links=html_saving_config.include_links,
                extraction_mode=html_saving_config.extraction_mode,
                detect_language=html_saving_config.detect_language,
                language_provider=html_saving_config.language_provider,
                language_model=html_saving_config.language_model,
                language_confidence_threshold=html_saving_config.language_confidence_threshold,
            )
            self.logger.info(f"HTML saving enabled: output_dir={html_saving_config.output_dir}, mode={html_saving_config.extraction_mode}")
            
            # Create Playwright fetcher if JS rendering is enabled
            if html_saving_config.use_playwright:
                self.playwright_fetcher = PlaywrightHtmlFetcher(
                    timeout=html_saving_config.playwright_timeout,
                    scroll_page=html_saving_config.scroll_page,
                    wait_for_idle=html_saving_config.wait_for_idle,
                    logger=self.logger,
                )
                self.playwright_concurrency = html_saving_config.playwright_concurrency
                self.logger.info(f"Playwright JS rendering enabled (concurrency={self.playwright_concurrency})")

    async def discover(self) -> List[str]:
        urls: List[str] = []

        if self.use_sitemap:
            try:
                urls = await SitemapDiscoverer(self.base_url).discover_urls()
            except Exception as e:
                self.logger.warning(f"Sitemap discover failed: {e}")

        if not urls:
            self.logger.info("No URLs from sitemap; falling back to HTTP crawler")
            
            # Use lower concurrency for Playwright (browsers are resource-heavy)
            concurrency_override = self.playwright_concurrency if self.playwright_fetcher else None
            
            crawler = HttpAsyncCrawler(
                self.base_url, 
                html_saver=self.html_saver,
                playwright_fetcher=self.playwright_fetcher,
                concurrency_override=concurrency_override,
            )
            urls = await crawler.run()
            await crawler.close()

        urls = [u for u in urls if isinstance(u, str) and u.startswith(("http://", "https://"))]
        return self._postprocess(urls)

    def _postprocess(self, links: List[str]) -> List[str]:
        unique = sorted(set(links))
        if self.post_cfg.collapse_language_variants:
            defaults = [""] + [l.strip().lower() for l in self.post_cfg.default_languages if l.strip()]
            unique = collapse_language_variants(unique, defaults, self.patterns)
        return unique
