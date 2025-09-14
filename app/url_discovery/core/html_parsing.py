from typing import Optional, Set

from bs4 import BeautifulSoup

from app.url_discovery.core.normalize import normalize_link
from app.url_discovery.core.patterns import ParsingPatterns


def is_probably_html_url(u: Optional[str], patterns: ParsingPatterns) -> bool:
    if not u:
        return False
    if patterns.non_html_api.search(u):
        return False
    lower = u.lower()
    for ext in patterns.asset_extensions:
        if lower.endswith("." + ext) or ("." + ext + "?") in lower:
            return False
    return True


def extract_links(
        base_url: str,
        html: str,
        include_assets: bool,
        html_only: bool,
        patterns: ParsingPatterns,
) -> Set[str]:
    soup = BeautifulSoup(html, "lxml")
    out: Set[str] = set()

    def add(u: Optional[str]) -> None:
        if not u:
            return
        if html_only and not is_probably_html_url(u, patterns):
            return
        out.add(u)

    for a in soup.select("a[href], link[href]"):
        add(normalize_link(base_url, a.get("href"), patterns))

    for a in soup.select('a[rel~=next], link[rel~=next], a[aria-label*="next" i]'):
        add(normalize_link(base_url, a.get("href"), patterns))

    if include_assets and not html_only:
        for tag, attr in (("img", "src"), ("script", "src"), ("iframe", "src"),
                          ("source", "src"), ("video", "src"), ("audio", "src")):
            for el in soup.select(f"{tag}[{attr}]"):
                add(normalize_link(base_url, el.get(attr), patterns))

        for el in soup.select("[srcset]"):
            srcset = el.get("srcset", "")
            for part in srcset.split(","):
                token = part.strip().split()[0]
                if token:
                    add(normalize_link(base_url, token, patterns))

    for script in soup.find_all("script"):
        content = script.string or script.get_text(strip=False) or ""
        if not content:
            continue
        for m in patterns.url_in_text.finditer(content):
            add(normalize_link(base_url, m.group("u"), patterns))

    return out
