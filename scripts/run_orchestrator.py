import argparse
import asyncio

from app.config.loaders.document_sweeping_config_loader import get_document_sweeping_config
from app.config.loaders.env_loader import env_settings
from app.config.loaders.helpers.yaml_loading_helper import load_yaml
from app.config.models.app_config_model import AppConfig
from app.crawlers.document_downloader.core.document_downloader import DocumentDownloader
from app.crawlers.url_discovery.orchestrator import UrlDiscoveryOrchestrator
from app.logging.logger import setup_logger


def main():
    parser = argparse.ArgumentParser(description="Run URL discovery and optionally download documents.")
    parser.add_argument("start_url", nargs="?",
                        help="Optional start URL; otherwise taken from test.target_url in config")
    parser.add_argument("--download", action="store_true",
                        help="After discovery, download documents using test.* settings")
    args = parser.parse_args()

    if args.start_url:
        start_url = args.start_url
    else:
        data = load_yaml(env_settings.get_config_path())
        cfg = AppConfig(**data)
        start_url = cfg.test.target_url

    logger = setup_logger(__name__)

    async def run():
        orch = UrlDiscoveryOrchestrator(start_url)
        urls = await orch.discover()
        logger.info(f"Discovery complete: total_urls={len(urls)} start_url={start_url}")
        for u in urls:
            logger.debug(f"URL: {u}")

        if args.download:
            sweep_cfg = get_document_sweeping_config()
            downloader = DocumentDownloader(
                output_dir=sweep_cfg.output_dir,
                allowed_mime_types=set([s.strip().lower() for s in sweep_cfg.doc_mime_types]),
                allowed_extensions=set([s.strip().lower().lstrip('.') for s in sweep_cfg.doc_extensions]),
                max_bytes=sweep_cfg.max_document_bytes,
                max_concurrency=sweep_cfg.max_concurrency,
                js_pages=sweep_cfg.js_pages,
                same_origin_only=sweep_cfg.same_origin_only,
            )
            logger.info("Starting document sweep...")
            downloaded = await downloader.sweep(urls)
            logger.info(f"Document sweep complete: downloaded={len(downloaded)} dir={sweep_cfg.output_dir}")
            for p in downloaded:
                logger.debug(f"FILE: {p}")

    asyncio.run(run())


if __name__ == "__main__":
    main()
