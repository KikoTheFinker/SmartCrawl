import hashlib
import mimetypes
import os
from urllib.parse import urlparse, urldefrag, unquote, parse_qs, urlencode


# Query parameters commonly used for tracking/cache-busting that don't
# change the actual document content.
_STRIP_PARAMS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "v", "ver", "version", "t", "ts", "timestamp", "cb", "cache",
    "ref", "fbclid", "gclid", "mc_cid", "mc_eid", "_ga", "nocache",
})


def normalize_doc_url(url: str) -> str:
    """Normalize document URLs for deduplication.

    Strips fragments and common tracking/cache-busting query parameters
    so that variant URLs pointing to the same document are treated as equal.
    """
    url, _ = urldefrag(url)
    parsed = urlparse(url)

    # Strip tracking / cache-busting query params
    if parsed.query:
        filtered = {
            k: v for k, v in parse_qs(parsed.query, keep_blank_values=True).items()
            if k.lower() not in _STRIP_PARAMS
        }
        clean_query = urlencode(filtered, doseq=True) if filtered else ""
    else:
        clean_query = ""

    clean = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
        path=unquote(parsed.path),
        query=clean_query,
    )
    return clean.geturl()


def sanitize_filename(url: str, content_type: str) -> str:
    """Generate safe filenames with hash prefix to avoid collisions."""
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    path = urlparse(url).path
    name = os.path.basename(path) or "file"
    if "." not in name:
        ext = mimetypes.guess_extension(content_type or "") or ""
        name = f"{name}{ext}"
    return f"{digest}_{name}"
