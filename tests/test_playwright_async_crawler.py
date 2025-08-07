import asyncio
from app.config.loaders.env_loader import env_settings
from app.config.loaders.helpers.yaml_loading_helper import load_yaml
from app.config.models.app_config_model import AppConfig
from app.url_discovery.playwright_async_crawler import AsyncPlaywrightCrawler


def test_playwright_async_crawler():
    async def run_test():
        config_data = load_yaml(env_settings.get_config_path())
        config = AppConfig(**config_data)

        crawler = AsyncPlaywrightCrawler(config.test.target_url)
        urls = await crawler.crawl()

        print(f"CRAWLED URLS: {urls}")

        assert isinstance(urls, list)
        assert all(url.startswith("http") for url in urls)
        assert all(config.test.target_url in url for url in urls)

    asyncio.run(run_test())


if __name__ == '__main__':
    test_playwright_async_crawler()
