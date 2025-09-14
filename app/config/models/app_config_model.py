from typing import List, Dict

from pydantic import BaseModel


class SitemapConfig(BaseModel):
    timeout: int
    retry: int
    concurrency: int
    common_paths: List[str]
    headers: Dict[str, str]
    max_urls_per_sitemap: int = 50000
    max_total_urls: int = 1000000
    worker_timeout: float = 30.0


class HttpCrawlerConfig(BaseModel):
    include_subdomains: bool
    include_assets: bool
    html_only: bool
    max_pages: int
    concurrency: int
    obey_robots: bool
    verbose: bool


class PostprocessConfig(BaseModel):
    collapse_language_variants: bool
    default_languages: List[str]


class ParsingConfig(BaseModel):
    html_content_types: List[str]
    sitemap_content_types: List[str]
    url_in_text_pattern: str
    asset_extensions: List[str]
    non_html_api_patterns: List[str]
    tracking_params: List[str]
    language_segment_pattern: str
    pagination_hints: List[str]
    max_url_length: int
    prefer_https: bool
    strip_www: bool
    max_pagination_page: int


class UrlDiscoveryConfig(BaseModel):
    sitemap: SitemapConfig
    crawler: HttpCrawlerConfig
    postprocess: PostprocessConfig
    parsing: ParsingConfig


class TestConfig(BaseModel):
    target_url: str


class AppConfig(BaseModel):
    test: TestConfig
    url_discovery: UrlDiscoveryConfig
