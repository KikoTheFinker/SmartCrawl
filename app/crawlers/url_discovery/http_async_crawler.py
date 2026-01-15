from typing import List, Optional

from app.config.loaders.url_discovery_config_loader import get_crawler_config, get_sitemap_config
from app.crawlers.url_discovery.core.base_crawler import BaseCrawler
from app.crawlers.url_discovery.utils.html_content_processor import HtmlContentSaver
from app.crawlers.url_discovery.utils.patterns import load_patterns
from app.crawlers.url_discovery.utils.playwright_fetcher import PlaywrightHtmlFetcher
from app.logging.logger import setup_logger


class HttpAsyncCrawler(BaseCrawler):
    """Public async crawler interface."""

    def __init__(self, start_url: str, html_saver: Optional[HtmlContentSaver] = None,
                 playwright_fetcher: Optional[PlaywrightHtmlFetcher] = None,
                 concurrency_override: Optional[int] = None):
        cfg = get_crawler_config()
        site_cfg = get_sitemap_config()
        patterns = load_patterns()
        logger = setup_logger(__name__)
        
        # Override concurrency if specified (e.g., for Playwright which needs lower concurrency)
        if concurrency_override is not None:
            cfg.concurrency = concurrency_override
            logger.info(f"Concurrency overridden to {concurrency_override}")
        
        super().__init__(start_url, cfg, site_cfg, patterns, logger, 
                         html_saver=html_saver, playwright_fetcher=playwright_fetcher)

    async def run(self) -> List[str]:
        return await super().run()
