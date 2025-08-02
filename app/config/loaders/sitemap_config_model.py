from typing import List, Dict

from pydantic import BaseModel


class SitemapConfig(BaseModel):
    timeout: int
    retry: int
    common_paths: List[str]
    headers: Dict[str, str]


class TestConfig(BaseModel):
    target_url: str


class AppConfig(BaseModel):
    sitemap: SitemapConfig
    test: TestConfig
