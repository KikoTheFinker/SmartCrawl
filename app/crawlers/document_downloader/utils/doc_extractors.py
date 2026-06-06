from typing import List, Tuple, Optional, Set
import hashlib
import os
import httpx
from selectolax.parser import HTMLParser
from urllib.parse import urljoin

from app.crawlers.document_downloader.utils.doc_filters import is_probably_js_rendered


# Common download button selectors for various download manager plugins
DOWNLOAD_BUTTON_SELECTORS = [
    # WordPress Download Manager
    ".wpdm-download-link",
    ".wpdm-btn",
    "[data-package]",
    ".wpdm_link",
    # Easy Digital Downloads
    ".edd-submit",
    ".edd-add-to-cart",
    # Generic download buttons
    "a.download",
    "a.btn-download",
    "button.download",
    ".download-button",
    ".download-btn",
    "[download]",
    # Text-based matching
    'a:has-text("Download")',
    'button:has-text("Download")',
    # Data attributes
    "[data-download]",
    "[data-file]",
    # Better File Download plugin
    ".bfd-download-link",
]


async def extract_links_httpx(client: httpx.AsyncClient, url: str) -> Tuple[List[str], bool]:
    try:
        resp = await client.get(url, follow_redirects=True, timeout=25)
    except (httpx.RequestError, httpx.TimeoutException):
        return [], False

    html = resp.text
    tree = HTMLParser(html)
    links: List[str] = []
    for a in tree.css("a[href]"):
        normalized = normalize_url(str(resp.url), a.attributes.get("href"))
        if normalized:
            links.append(normalized)
    unique = list(dict.fromkeys(links))
    return unique, is_probably_js_rendered(html)


async def extract_with_playwright(context, url: str, scroll_rounds: int = 2,
                                  idle: str = "networkidle") -> Tuple[str, List[str], List[Tuple[str, str]]]:
    links: List[str] = []
    responses: List[Tuple[str, str]] = []
    page = await context.new_page()
    page.on("response", lambda resp: responses.append(
        (resp.url, (resp.headers.get("content-type") or "").split(";")[0].lower())
    ))
    await page.goto(url, wait_until=idle, timeout=45000)
    for _ in range(scroll_rounds):
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(800)
    anchors = await page.eval_on_selector_all("a[href]", "els => els.map(e => e.getAttribute('href'))")
    for href in anchors:
        normalized = normalize_url(page.url, href)
        if normalized:
            links.append(normalized)
    html = await page.content()
    await page.close()
    return html, list(dict.fromkeys(links)), responses


def _hash_file(path: str) -> str:
    """Compute SHA-256 digest of a file on disk."""
    sha256 = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


async def click_download_buttons(
    context, 
    url: str, 
    output_dir: str,
    allowed_extensions: set,
    logger=None,
    seen_hashes: Optional[Set[str]] = None,
) -> List[str]:
    """
    Click download buttons on a page and capture any file downloads.
    
    This handles JavaScript-based download managers that don't use direct links.
    Returns list of downloaded file paths.
    
    If *seen_hashes* is provided, each downloaded file is hash-checked
    and removed if it duplicates an already-seen document.
    """
    downloaded_files: List[str] = []
    page = await context.new_page()
    
    try:
        # Navigate to page
        await page.goto(url, wait_until="networkidle", timeout=45000)
        await page.wait_for_timeout(1000)  # Wait for JS to initialize
        
        # Find all download buttons
        found_buttons = []
        for selector in DOWNLOAD_BUTTON_SELECTORS:
            try:
                elements = await page.query_selector_all(selector)
                for elem in elements:
                    if await elem.is_visible():
                        found_buttons.append(elem)
            except Exception:
                continue
        
        if logger:
            logger.info(f"Found {len(found_buttons)} download buttons on {url}")
        
        # Click each button and capture downloads
        for i, button in enumerate(found_buttons[:10]):  # Limit to 10 buttons per page
            try:
                # Set up download handling
                async with page.expect_download(timeout=15000) as download_info:
                    await button.click()
                
                download = await download_info.value
                
                # Check if file extension is allowed
                filename = download.suggested_filename
                ext = os.path.splitext(filename)[1].lstrip('.').lower()
                
                if ext in allowed_extensions:
                    os.makedirs(output_dir, exist_ok=True)
                    save_path = os.path.join(output_dir, filename)
                    
                    # Handle duplicate filenames
                    counter = 1
                    base, extension = os.path.splitext(save_path)
                    while os.path.exists(save_path):
                        save_path = f"{base}_{counter}{extension}"
                        counter += 1
                    
                    await download.save_as(save_path)

                    # --- content-hash deduplication ---
                    if seen_hashes is not None:
                        digest = _hash_file(save_path)
                        if digest in seen_hashes:
                            os.remove(save_path)
                            if logger:
                                logger.debug(f"Skip duplicate by content (JS click): {filename}")
                            continue
                        seen_hashes.add(digest)

                    downloaded_files.append(save_path)
                    if logger:
                        logger.info(f"Downloaded (via click): {filename} -> {save_path}")
                else:
                    await download.cancel()
                    if logger:
                        logger.debug(f"Skipped download (extension {ext} not allowed): {filename}")
                        
            except Exception as e:
                # No download triggered by this button, that's okay
                if logger:
                    logger.debug(f"Button {i} didn't trigger download: {str(e)[:50]}")
                continue
                
    except Exception as e:
        # Suppress scary traceback if it's just a timeout
        if "Timeout" in str(e):
            if logger:
                logger.debug(f"Timeout clicking download buttons on {url}: {e}")
        else:
            if logger:
                logger.warning(f"Error clicking download buttons on {url}: {e}")
    finally:
        await page.close()
    
    return downloaded_files


async def intercept_downloads_on_page(
    context,
    url: str,
    output_dir: str,
    allowed_mime_types: set,
    allowed_extensions: set,
    logger=None,
) -> List[str]:
    """
    Navigate to page and intercept any document downloads that happen.
    
    This captures files served via AJAX/fetch that match allowed MIME types.
    """
    downloaded_files: List[str] = []
    page = await context.new_page()
    
    async def handle_response(response):
        """Intercept responses and save documents."""
        try:
            content_type = (response.headers.get("content-type") or "").split(";")[0].lower()
            
            # Check if this is a document we want
            if content_type not in allowed_mime_types:
                return
            
            # Get the URL and try to extract filename
            resp_url = response.url
            filename = resp_url.split("/")[-1].split("?")[0]
            
            # Check extension
            ext = os.path.splitext(filename)[1].lstrip('.').lower()
            if ext not in allowed_extensions:
                # Try to determine from content-type
                ext_map = {
                    "application/pdf": "pdf",
                    "application/msword": "doc",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
                    "application/vnd.ms-excel": "xls",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
                }
                ext = ext_map.get(content_type, "")
                if ext:
                    filename = f"{filename}.{ext}" if not filename.endswith(f".{ext}") else filename
            
            if ext not in allowed_extensions:
                return
            
            # Download the content
            try:
                body = await response.body()
                if len(body) < 100:  # Too small to be a real document
                    return
                    
                os.makedirs(output_dir, exist_ok=True)
                save_path = os.path.join(output_dir, filename)
                
                # Handle duplicates
                counter = 1
                base, extension = os.path.splitext(save_path)
                while os.path.exists(save_path):
                    save_path = f"{base}_{counter}{extension}"
                    counter += 1
                
                with open(save_path, "wb") as f:
                    f.write(body)
                
                downloaded_files.append(save_path)
                if logger:
                    logger.info(f"Intercepted download: {resp_url} -> {save_path}")
            except Exception:
                pass
                
        except Exception:
            pass
    
    page.on("response", handle_response)
    
    try:
        await page.goto(url, wait_until="networkidle", timeout=45000)
        # Scroll to trigger lazy loads
        for _ in range(3):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1000)
    except Exception as e:
        if logger:
            logger.warning(f"Error intercepting downloads on {url}: {e}")
    finally:
        await page.close()
    
    return downloaded_files


def normalize_url(base: str, href: str) -> Optional[str]:
    if not href:
        return None
    href = href.strip()
    if href.startswith(("mailto:", "javascript:", "#")):
        return None
    return urljoin(base, href)
