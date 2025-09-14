from app.url_discovery.core.sitemap_processor import SitemapDiscoveryProcessor


class SitemapDiscoverer:
    def __init__(self, base_url: str):
        self.processor = SitemapDiscoveryProcessor(base_url)

    async def discover_urls(self) -> list[str]:
        return await self.processor.discover_urls()

    async def close(self):
        await self.processor.close()
