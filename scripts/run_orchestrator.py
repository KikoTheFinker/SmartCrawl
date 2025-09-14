import asyncio
import sys

from app.config.loaders.env_loader import env_settings
from app.config.loaders.helpers.yaml_loading_helper import load_yaml
from app.config.models.app_config_model import AppConfig
from app.logging.logger import setup_logger
from app.url_discovery.orchestrator import UrlDiscoveryOrchestrator


def main():
    logger = setup_logger(__name__)
    start_url = None
    if len(sys.argv) >= 2:
        start_url = sys.argv[1]
        logger.info(f"Using start_url from CLI: {start_url}")
    else:
        data = load_yaml(env_settings.get_config_path())
        cfg = AppConfig(**data)
        start_url = cfg.test.target_url
        logger.info(f"Using start_url from config: {start_url}")

    async def run():
        orchestrator = UrlDiscoveryOrchestrator(start_url)
        logger.info("Starting URL discovery...")
        urls = await orchestrator.discover()
        for u in urls:
            logger.info(f"Discovered: {u}")
        logger.info(f"TOTAL={len(urls)}")

    asyncio.run(run())


if __name__ == "__main__":
    main()
