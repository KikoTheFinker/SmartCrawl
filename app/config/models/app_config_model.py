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
    use_sitemap: bool = True


class DocumentSweepingConfig(BaseModel):
    output_dir: str = "downloads"
    max_concurrency: int = 16
    js_pages: int = 4
    same_origin_only: bool = True
    doc_extensions: List[str]
    doc_mime_types: List[str]
    max_document_bytes: int
    click_download_buttons: bool = True  # Click JS download buttons (WordPress Download Manager, etc.)


class HtmlSavingConfig(BaseModel):
    """Configuration for saving and processing HTML content."""
    enabled: bool = False
    output_dir: str = "html_output"
    save_raw: bool = True
    save_processed: bool = True
    output_format: str = "txt"  # txt, markdown
    include_tables: bool = True
    include_links: bool = False
    min_content_length: int = 100
    extraction_mode: str = "full_text"  # "main_content" (article only) or "full_text" (all visible text)
    
    # JavaScript rendering options (uses Playwright)
    use_playwright: bool = False  # Enable JS rendering for dynamic sites
    playwright_timeout: int = 30000  # Page load timeout in ms
    scroll_page: bool = True  # Scroll page to trigger lazy loading
    wait_for_idle: bool = True  # Wait for network idle before capturing
    playwright_concurrency: int = 4  # Max parallel browser pages (lower than httpx)


class AppConfig(BaseModel):
    test: TestConfig
    url_discovery: UrlDiscoveryConfig
    html_saving: HtmlSavingConfig = HtmlSavingConfig()