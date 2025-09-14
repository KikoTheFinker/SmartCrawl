from typing import List

from app.url_discovery.core.crawler import HttpAsyncCrawler as _CoreCrawler


class HttpAsyncCrawler(_CoreCrawler):
    async def run(self) -> List[str]:
        return await super().run()
