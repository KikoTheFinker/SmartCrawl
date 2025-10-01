from typing import List

from app.config.loaders.url_discovery_config_loader import get_crawler_config, get_sitemap_config
from app.crawlers.url_discovery.core.base_crawler import BaseCrawler
from app.crawlers.url_discovery.utils.patterns import load_patterns
from app.logging.logger import setup_logger


class HttpAsyncCrawler(BaseCrawler):
    """Public async crawler interface."""

    def __init__(self, start_url: str):
        cfg = get_crawler_config()
        site_cfg = get_sitemap_config()
        patterns = load_patterns()
        logger = setup_logger(__name__)
        super().__init__(start_url, cfg, site_cfg, patterns, logger)

    async def run(self) -> List[str]:
        return await super().run()
