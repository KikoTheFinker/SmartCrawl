from app.config.loaders.test_config_loader import get_test_config
from app.url_discovery.sitemap_discoverer import SitemapDiscoverer


def test_sitemap_discoverer():
    target_config = get_test_config()

    discoverer = SitemapDiscoverer(target_config.target_url)
    urls = discoverer.discover_urls()
    print(f"URLS FOUND: {urls}")

    assert isinstance(urls, list)
    assert all(url.startswith("http") for url in urls)


if __name__ == '__main__':
    test_sitemap_discoverer()
