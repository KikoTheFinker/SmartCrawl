import asyncio
import hashlib
import os
from typing import Iterable, List, Optional, Set
from urllib.parse import urlparse

import httpx
from playwright.async_api import async_playwright

from app.crawlers.document_downloader.utils.doc_download import download_file
from app.crawlers.document_downloader.utils.doc_extractors import (
    extract_links_httpx, 
    extract_with_playwright,
    click_download_buttons,
)
from app.crawlers.document_downloader.utils.doc_filters import looks_like_doc_by_ext
from app.crawlers.document_downloader.utils.doc_normalization import normalize_doc_url
from app.logging.logger import setup_logger
from app.utils.robots_cache import robots_cache


class DocumentDownloader:
    def __init__(
            self,
            output_dir: str,
            allowed_mime_types: Set[str],
            allowed_extensions: Set[str],
            max_bytes: int,
            max_concurrency: int,
            js_pages: int,
            same_origin_only: bool,
            click_download_buttons: bool = True,  # NEW: click JS download buttons
    ) -> None:
        self.output_dir = output_dir
        self.allowed_mime_types = {m.lower() for m in allowed_mime_types}
        self.allowed_extensions = {e.lower().lstrip('.') for e in allowed_extensions}
        self.max_bytes = int(max_bytes)
        self.max_concurrency = max(1, int(max_concurrency))
        self.js_pages = max(0, int(js_pages))
        self.same_origin_only = bool(same_origin_only)
        self.click_download_buttons_enabled = click_download_buttons
        self.logger = setup_logger(__name__)
        self._global_seen_docs: Set[str] = set()
        self._global_seen_hashes: Set[str] = set()
        self._seen_lock = asyncio.Lock()
        self._bootstrap_existing_hashes()

    def _bootstrap_existing_hashes(self) -> None:
        """
        Preload hashes from already downloaded files so future runs
        skip exact duplicates that are already on disk.
        """
        if not os.path.isdir(self.output_dir):
            return
        for name in os.listdir(self.output_dir):
            path = os.path.join(self.output_dir, name)
            if not os.path.isfile(path):
                continue
            try:
                sha = hashlib.sha256()
                with open(path, "rb") as f:
                    for chunk in iter(lambda: f.read(8192), b""):
                        sha.update(chunk)
                self._global_seen_hashes.add(sha.hexdigest())
            except Exception:
                continue

    async def sweep(self, urls: Iterable[str]) -> List[str]:
        url_list = list(urls)
        if not url_list:
            return []

        start_netloc = urlparse(url_list[0]).netloc if self.same_origin_only else None
        sem = asyncio.Semaphore(self.max_concurrency)
        results: List[str] = []

        self.logger.info(
            f"Doc sweep start: urls={len(url_list)}, out={self.output_dir}, same_origin_only={self.same_origin_only}"
        )

        async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=20,
                headers={"User-Agent": "SmartCrawl/1.0"},
        ) as client, async_playwright() as pw:

            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(ignore_https_errors=True)

            try:
                async def task(url: str):
                    async with sem:
                        return await self._for_url(url, client, context, start_netloc)

                path_lists = await asyncio.gather(
                    *[task(u) for u in url_list], return_exceptions=True
                )
            finally:
                await context.close()
                await browser.close()

        errors = 0
        for item in path_lists:
            if isinstance(item, list):
                results.extend(item)
            elif isinstance(item, Exception):
                errors += 1

        self.logger.info(
            f"Doc sweep done: downloaded={len(results)} errors={errors}"
        )
        return list(dict.fromkeys(results))

    async def _for_url(
            self,
            url: str,
            client: httpx.AsyncClient,
            context,
            start_netloc: Optional[str],
    ) -> List[str]:
        if not await robots_cache.allowed(url, client):
            self.logger.info(f"Skip page (robots): {url}")
            return []

        links, looks_js = await extract_links_httpx(client, url)
        doc_candidates = [
            u for u in links if looks_like_doc_by_ext(u, self.allowed_extensions)
        ]
        
        # Try clicking download buttons first (for JS download managers)
        js_downloaded: List[str] = []
        if context and self.click_download_buttons_enabled:
            try:
                js_downloaded = await click_download_buttons(
                    context,
                    url,
                    self.output_dir,
                    self.allowed_extensions,
                    self.logger,
                    seen_hashes=self._global_seen_hashes,
                )
                if js_downloaded:
                    self.logger.info(f"Downloaded {len(js_downloaded)} files via JS buttons from {url}")
            except Exception as e:
                self.logger.debug(f"Click download buttons failed for {url}: {e}")
        
        # If no direct doc links found and page looks JS-rendered, try Playwright extraction
        if context and not doc_candidates and looks_js:
            self.logger.debug(f"Trying Playwright for {url} (httpx found no docs)")
            _, links_js, responses = await extract_with_playwright(context, url)
            links = list(dict.fromkeys(links + links_js))
            for u, content_type in responses:
                if (
                        (content_type or "").lower() in self.allowed_mime_types
                        or looks_like_doc_by_ext(u, self.allowed_extensions)
                ):
                    doc_candidates.append(u)

        for u in links:
            if looks_like_doc_by_ext(u, self.allowed_extensions):
                doc_candidates.append(u)

        doc_candidates = [u for u in dict.fromkeys(doc_candidates)]
        self.logger.info(
            f"Page scanned: {url} candidates={len(doc_candidates)} js={looks_js} js_downloads={len(js_downloaded)}"
        )

        downloaded: List[str] = list(js_downloaded)  # Start with JS-downloaded files

        for doc_url in doc_candidates:
            norm_url = normalize_doc_url(doc_url)

            # Eagerly reserve the URL under lock to prevent concurrent duplicates
            async with self._seen_lock:
                if norm_url in self._global_seen_docs:
                    self.logger.debug(f"Skip duplicate (already seen): {norm_url}")
                    continue
                self._global_seen_docs.add(norm_url)

            if self.same_origin_only and start_netloc and urlparse(norm_url).netloc != start_netloc:
                self.logger.debug(f"Skip candidate (cross-origin): {norm_url}")
                continue
            if not await robots_cache.allowed(norm_url, client):
                self.logger.debug(f"Skip candidate (robots): {norm_url}")
                continue

            path = await download_file(
                client,
                norm_url,
                self.output_dir,
                self.allowed_mime_types,
                self.max_bytes,
                self._global_seen_hashes,
                self.logger,
            )
            if path:
                downloaded.append(path)
                self.logger.info(f"Downloaded: {norm_url} -> {path}")

        return downloaded
