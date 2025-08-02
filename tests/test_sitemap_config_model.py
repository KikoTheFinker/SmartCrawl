from app.config.loaders.env_loader import env_settings
from app.config.loaders.helpers.yaml_loading_helper import load_yaml
from app.config.loaders.sitemap_config_model import AppConfig
from app.url_discovery.sitemap_discoverer import SitemapDiscoverer


def test_discover_urls_live():
    config_data = load_yaml(env_settings.get_config_path())
    config = AppConfig(**config_data)

    discoverer = SitemapDiscoverer(config.test.target_url, config)
    urls = discoverer.discover_urls()
    print(f"URLS FOUND: {urls}")

    assert isinstance(urls, list)
    assert all(url.startswith("http") for url in urls)


if __name__ == '__main__':
    test_discover_urls_live()
