#!/usr/bin/env python3
import argparse
import asyncio
import sys
import os
from pathlib import Path

# Add project root to sys.path to allow imports from 'app'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config.loaders.document_sweeping_config_loader import get_document_sweeping_config
from app.config.loaders.env_loader import env_settings
from app.config.loaders.helpers.yaml_loading_helper import load_yaml
from app.config.loaders.html_saving_config_loader import get_html_saving_config
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
    parser.add_argument("--process-docs", action="store_true",
                        help="Process downloaded documents with docling")
    parser.add_argument("--docling-format", choices=["markdown", "html", "json"],
                        default="markdown",
                        help="Output format for docling processing (default: markdown)")
    parser.add_argument("--save-html", action="store_true",
                        help="Save raw HTML and processed content (uses html_saving config)")
    parser.add_argument("--use-playwright", action="store_true",
                        help="Use Playwright for JS rendering (slower but captures dynamic content)")
    parser.add_argument("--enable-ocr", action="store_true",
                        help="Enable OCR (Optical Character Recognition) for scanned documents and images")
    parser.add_argument("--disable-ocr", action="store_true",
                        help="Disable OCR (OCR is enabled by default when --process-docs is used)")
    parser.add_argument("--ocr-languages", nargs="+", default=None,
                        help="OCR language codes (e.g., 'en' for English, 'es' for Spanish). Default: ['en']")
    args = parser.parse_args()

    # Load config
    data = load_yaml(env_settings.get_config_path())
    cfg = AppConfig(**data)
    
    if args.start_url:
        start_url = args.start_url
    else:
        start_url = cfg.test.target_url
    
    # Get use_sitemap from config
    use_sitemap = cfg.test.use_sitemap

    logger = setup_logger(__name__)

    # Get HTML saving config if flag is set
    html_saving_config = None
    if args.save_html or args.use_playwright:
        html_saving_config = get_html_saving_config()
        # Force enable if flags are used
        if args.save_html:
            html_saving_config.enabled = True
            logger.info(f"HTML saving enabled: output={html_saving_config.output_dir}")
        if args.use_playwright:
            html_saving_config.enabled = True
            html_saving_config.use_playwright = True
            logger.info("Playwright JS rendering enabled (captures dynamic/JS-loaded content)")
        # When saving HTML, we need to use HTTP crawler (not sitemap) to actually fetch pages
        if use_sitemap:
            logger.info("Note: use_sitemap=true but --save-html requires HTTP crawler. Disabling sitemap.")
            use_sitemap = False

    async def run():
        orch = UrlDiscoveryOrchestrator(
            start_url,
            use_sitemap=use_sitemap,
            html_saving_config=html_saving_config
        )
        urls = await orch.discover()
        logger.info(f"Discovery complete: total_urls={len(urls)} start_url={start_url}")
        for u in urls:
            logger.debug(f"URL: {u}")

        downloaded = []
        if args.download or args.process_docs:
            sweep_cfg = get_document_sweeping_config()

        if args.download:
            downloader = DocumentDownloader(
                output_dir=sweep_cfg.output_dir,
                allowed_mime_types=set([s.strip().lower() for s in sweep_cfg.doc_mime_types]),
                allowed_extensions=set([s.strip().lower().lstrip('.') for s in sweep_cfg.doc_extensions]),
                max_bytes=sweep_cfg.max_document_bytes,
                max_concurrency=sweep_cfg.max_concurrency,
                js_pages=sweep_cfg.js_pages,
                same_origin_only=sweep_cfg.same_origin_only,
                click_download_buttons=sweep_cfg.click_download_buttons,
            )
            logger.info(f"Starting document sweep (click_buttons={sweep_cfg.click_download_buttons})...")
            downloaded = await downloader.sweep(urls)
            logger.info(f"Document sweep complete: downloaded={len(downloaded)} dir={sweep_cfg.output_dir}")
            for p in downloaded:
                logger.debug(f"FILE: {p}")

        # Step 3: Document Processing with Docling (if requested)
        if args.process_docs:
            logger.info("=" * 60)
            logger.info("Step 3: Document Processing with Docling")
            logger.info("=" * 60)
            
            input_dir = sweep_cfg.output_dir
            input_path = Path(input_dir)
            
            existing_docs = [f for f in input_path.glob("*.*") if f.is_file() and f.parent.name != "processed"] if input_path.exists() else []
            
            if not existing_docs:
                logger.warning(f"No documents found in {input_dir}. Skipping docling processing.")
            else:
                # Create output directory for processed documents
                output_dir = input_path / "processed" / args.docling_format
                output_dir.mkdir(parents=True, exist_ok=True)
                
                # Enable OCR by default when processing documents, unless explicitly disabled
                enable_ocr = (args.enable_ocr or not args.disable_ocr)
                
                # Import DoclingProcessor here to avoid heavy imports on startup when not processing docs
                from app.docling.docling_processor import DoclingProcessor
                
                processor = DoclingProcessor(
                    input_dir=str(input_path),
                    output_dir=str(output_dir),
                    export_format=args.docling_format,
                    concurrency=2,
                    enable_ocr=enable_ocr,
                    ocr_languages=args.ocr_languages,
                    detect_language=sweep_cfg.detect_language,
                    language_provider=sweep_cfg.language_provider,
                    language_model=sweep_cfg.language_model,
                    language_confidence_threshold=sweep_cfg.language_confidence_threshold,
                )
                
                processed_files = await processor.process_all()
                logger.info(f"Processed {len(processed_files)} documents to {output_dir}")

    asyncio.run(run())


if __name__ == "__main__":
    main()
