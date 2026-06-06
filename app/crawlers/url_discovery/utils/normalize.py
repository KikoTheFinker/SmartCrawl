from typing import Tuple, Union, Optional

from app.crawlers.url_discovery.utils.patterns import ParsingPatterns


def canonical_netloc(scheme: str, netloc: str, strip_www: bool, prefer_https: bool) -> Tuple[str, str]:
    nl = netloc.lower()
    if strip_www and nl.startswith("www."):
        nl = nl[4:]
    sch = "https" if prefer_https else scheme
    if nl.endswith(":80") and sch == "http":
        nl = nl[:-3]
    if nl.endswith(":443") and sch == "https":
        nl = nl[:-4]
    return sch, nl


from urllib.parse import urljoin, urldefrag, urlparse, urlunparse, parse_qsl, urlencode


def normalize_link(
        base_url: str,
        href: Union[str, bytes, None],
        patterns: ParsingPatterns
) -> Optional[str]:
    if not href:
        return None
    if isinstance(href, (bytes, bytearray)):
        try:
            href = href.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            href = href.decode("utf-8", errors="ignore")

    href = href.strip()
    if href.lower().startswith(("mailto:", "tel:", "javascript:", "data:", "about:blank", "#")):
        return None

    if "\\/" in href:
        href = href.replace("\\/", "/")

    if href.startswith("//"):
        base_scheme = urlparse(base_url).scheme or ("https" if patterns.prefer_https else "http")
        href = f"{base_scheme}:{href}"

    if len(href) > patterns.max_url_length or "\\" in href:
        return None

    url = urljoin(base_url, href)
    url, _ = urldefrag(url)
    p = urlparse(url)
    if p.scheme not in ("http", "https"):
        return None

    sch, nl = canonical_netloc(p.scheme, p.netloc, patterns.strip_www, patterns.prefer_https)

    path = p.path or "/"
    if path != "/":
        while "//" in path:
            path = path.replace("//", "/")

    q_pairs: list[tuple[str, str]] = []
    for k, v in parse_qsl(p.query, keep_blank_values=True):
        kl = k.lower()
        if kl in patterns.asset_extensions or kl in patterns.pagination_hints or kl in patterns.tracking_params:
            continue
        q_pairs.append((k, v))

    query = urlencode(q_pairs, doseq=True)

    out = urlunparse((sch, nl, path, "", query, ""))
    if len(out) > patterns.max_url_length:
        return None
    return out


def same_domain(url: str, root_netloc: str, include_subdomains: bool) -> bool:
    netloc = urlparse(url).netloc.lower()
    root = root_netloc.lower()

    # Handle www variations: treat www.example.com and example.com as the same
    root_without_www = root[4:] if root.startswith("www.") else root
    netloc_without_www = netloc[4:] if netloc.startswith("www.") else netloc
    
    # Compare without www
    if root_without_www == netloc_without_www:
        return True

    # Original comparison (with www)
    if netloc == root:
        return True

    # Subdomain check
    if include_subdomains:
        # Check if netloc is a subdomain of root (without www)
        if netloc.endswith("." + root_without_www):
            return True
        # Check if root is a subdomain of netloc (without www)
        if root_without_www.endswith("." + netloc_without_www):
            return True

    return False


