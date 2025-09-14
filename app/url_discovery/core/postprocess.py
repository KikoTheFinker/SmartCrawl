from collections import defaultdict
from typing import DefaultDict, Dict, Iterable, List, Tuple
from urllib.parse import urlparse

from app.url_discovery.core.patterns import ParsingPatterns


def _split_lang(path: str, patterns: ParsingPatterns) -> Tuple[str, str]:
    if not path:
        return "", ""
    m = patterns.language_segment.match(path)
    if m:
        lang = m.group(1).lower()
        rest = path[len(m.group(0)) - 1:]
        return lang, rest
    return "", path


def collapse_language_variants(urls: Iterable[str], default_langs: Iterable[str], patterns: ParsingPatterns,
                               treat_assets_as_is: bool = True) -> List[str]:
    defaults = {l.lower() for l in default_langs}
    buckets: DefaultDict[Tuple[str, str, str], Dict[str, str]] = defaultdict(dict)
    assets: List[str] = []
    for u in urls:
        p = urlparse(u)
        path = p.path or "/"
        low = u.lower()
        if treat_assets_as_is and any(low.endswith("." + ext) for ext in patterns.asset_extensions):
            assets.append(u)
            continue
        lang, rest = _split_lang(path, patterns)
        if rest != "/" and rest.endswith("/"):
            rest = rest.rstrip("/")
        key = (p.scheme, p.netloc.lower(), rest)
        buckets[key][lang] = u
    out: List[str] = []
    for _, language_map in buckets.items():
        non_default = [u for lg, u in language_map.items() if lg and lg not in defaults]
        out.extend(sorted(set(non_default if non_default else language_map.values())))
    out.extend(assets)
    return sorted(set(out))
