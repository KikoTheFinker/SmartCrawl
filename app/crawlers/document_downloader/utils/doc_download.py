import os
import hashlib
from typing import Optional, Set, Tuple
import httpx

from app.crawlers.document_downloader.utils.doc_normalization import sanitize_filename


async def head_or_get_content_type(client: httpx.AsyncClient, url: str) -> Tuple[Optional[str], Optional[int]]:
    """Try HEAD first, then fallback to GET (range request) to determine content-type and length."""
    def _parse(r: httpx.Response) -> Tuple[Optional[str], Optional[int]]:
        content_type = r.headers.get("content-type")
        content_length = int(r.headers.get("content-length", "0") or 0) or None
        if r.status_code < 400 and content_type:
            return content_type.split(";")[0].strip().lower(), content_length
        return None, None

    try:
        head_resp = await client.head(url, follow_redirects=True, timeout=20)
        ct, cl = _parse(head_resp)
        if ct:
            return ct, cl
    except (httpx.RequestError, httpx.TimeoutException):
        pass

    try:
        get_resp = await client.get(url, follow_redirects=True, timeout=20, headers={"Range": "bytes=0-0"})
        ct, cl = _parse(get_resp)
        if ct:
            return ct, cl
    except (httpx.RequestError, httpx.TimeoutException):
        pass

    return None, None


async def download_file(
    client: httpx.AsyncClient,
    url: str,
    output_dir: str,
    allowed_mime_types: set,
    max_bytes: int,
    seen_hashes: Set[str],
    logger,
) -> Optional[str]:
    """Download a file if allowed by MIME and size, deduplicate by hash."""
    content_type, content_length = await head_or_get_content_type(client, url)
    if content_type and content_type.lower() not in allowed_mime_types:
        return None
    if content_length and content_length > max_bytes:
        return None

    os.makedirs(output_dir, exist_ok=True)
    try:
        async with client.stream("GET", url, follow_redirects=True, timeout=60) as resp:
            if resp.status_code >= 400:
                return None
            filename = sanitize_filename(str(resp.url), resp.headers.get("content-type") or "")
            path = os.path.join(output_dir, filename)

            sha256 = hashlib.sha256()
            total = 0
            with open(path, "wb") as fh:
                async for chunk in resp.aiter_bytes():
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > max_bytes:
                        return None
                    sha256.update(chunk)
                    fh.write(chunk)

            digest = sha256.hexdigest()
            if digest in seen_hashes:
                logger.debug(f"Skip duplicate by content: {url}")
                os.remove(path)
                return None
            seen_hashes.add(digest)
            return path
    except (httpx.RequestError, httpx.TimeoutException) as exc:
        logger.debug(f"HTTP error downloading {url}: {exc}")
        return None
    except OSError as exc:
        logger.debug(f"Filesystem error saving {url}: {exc}")
        return None
