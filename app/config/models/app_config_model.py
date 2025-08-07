from pydantic import BaseModel
from typing import List, Dict


class SitemapConfig(BaseModel):
    timeout: int
    retry: int
    common_paths: List[str]
    headers: Dict[str, str]


class PlaywrightCrawlerConfig(BaseModel):
    max_pages: int
    concurrency: int
    timeout: int
    load_state: str


class UrlDiscoveryConfig(BaseModel):
    sitemap: SitemapConfig
    crawler: PlaywrightCrawlerConfig


class TestConfig(BaseModel):
    target_url: str


class AppConfig(BaseModel):
    test: TestConfig
    url_discovery: UrlDiscoveryConfig
