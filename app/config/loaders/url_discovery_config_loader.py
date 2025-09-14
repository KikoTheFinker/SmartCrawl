from app.config.loaders.env_loader import env_settings
from app.config.loaders.helpers.yaml_loading_helper import load_yaml
from app.config.models.app_config_model import AppConfig, SitemapConfig, HttpCrawlerConfig, PostprocessConfig, \
    ParsingConfig


def get_sitemap_config() -> SitemapConfig:
    data = load_yaml(env_settings.get_config_path())
    return AppConfig(**data).url_discovery.sitemap


def get_crawler_config() -> HttpCrawlerConfig:
    data = load_yaml(env_settings.get_config_path())
    return AppConfig(**data).url_discovery.crawler


def get_postprocess_config() -> PostprocessConfig:
    data = load_yaml(env_settings.get_config_path())
    return AppConfig(**data).url_discovery.postprocess


def get_parsing_config() -> ParsingConfig:
    data = load_yaml(env_settings.get_config_path())
    return AppConfig(**data).url_discovery.parsing
