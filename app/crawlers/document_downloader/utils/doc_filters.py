import os
from urllib.parse import urlparse


def looks_like_doc_by_ext(url: str, allowed_extensions: set) -> bool:
    """Check if URL has an extension matching allowed docs."""
    path = urlparse(url).path.lower()
    _, ext = os.path.splitext(path)
    return ext.lstrip('.') in allowed_extensions


def is_probably_js_rendered(html: str) -> bool:
    """Heuristic to detect JS-heavy pages."""
    text = "".join(html.split())
    return len(text.strip()) < 400 and ("<script" in html.lower() or 'id="app"' in html.lower())
