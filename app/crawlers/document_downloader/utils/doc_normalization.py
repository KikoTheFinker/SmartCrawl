import hashlib
import mimetypes
import os
from urllib.parse import urlparse, urldefrag, unquote


def normalize_doc_url(url: str) -> str:
    """Normalize document URLs for deduplication."""
    url, _ = urldefrag(url)
    parsed = urlparse(url)
    clean = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
        path=unquote(parsed.path)
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
