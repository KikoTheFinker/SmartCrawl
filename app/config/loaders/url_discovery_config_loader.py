from app.config.loaders.env_loader import env_settings
from app.config.loaders.helpers.yaml_loading_helper import load_yaml
from app.config.models.app_config_model import AppConfig, SitemapConfig, PlaywrightCrawlerConfig


def get_sitemap_config() -> SitemapConfig:
    data = load_yaml(env_settings.get_config_path())
    return AppConfig(**data).url_discovery.sitemap


def get_crawler_config() -> PlaywrightCrawlerConfig:
    data = load_yaml(env_settings.get_config_path())
    return AppConfig(**data).url_discovery.crawler
