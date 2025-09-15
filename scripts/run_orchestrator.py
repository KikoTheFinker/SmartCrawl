import argparse
import asyncio

from app.config.loaders.env_loader import env_settings
from app.config.loaders.helpers.yaml_loading_helper import load_yaml
from app.config.models.app_config_model import AppConfig
from app.logging.logger import setup_logger
from app.url_discovery.orchestrator import UrlDiscoveryOrchestrator


def main():
    parser = argparse.ArgumentParser(description="SmartCrawl URL discovery")
    parser.add_argument(
        "start_url",
        nargs="?",
        help="Start URL (overrides config if provided)",
    )
    parser.add_argument(
        "--no-sitemap",
        action="store_true",
        help="Skip sitemap discovery and use HTTP crawler only",
    )
    args = parser.parse_args()

    logger = setup_logger(__name__)

    if args.start_url:
        start_url = args.start_url
        logger.info(f"Using start_url from CLI: {start_url}")
    else:
        data = load_yaml(env_settings.get_config_path())
        cfg = AppConfig(**data)
        start_url = cfg.test.target_url
        logger.info(f"Using start_url from config: {start_url}")

    async def run():
        orchestrator = UrlDiscoveryOrchestrator(start_url, use_sitemap=not args.no_sitemap)
        logger.info("Starting URL discovery...")
        urls = await orchestrator.discover()
        for u in urls:
            logger.info(f"Discovered: {u}")
        logger.info(f"TOTAL={len(urls)}")

    asyncio.run(run())


if __name__ == "__main__":
    main()
