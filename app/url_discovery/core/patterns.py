import re
from dataclasses import dataclass
from typing import Pattern, Set

from app.config.loaders.url_discovery_config_loader import get_parsing_config


@dataclass(frozen=True)
class ParsingPatterns:
    html_ct: Pattern[str]
    sitemap_ct: Pattern[str]
    url_in_text: Pattern[str]
    asset_extensions: Set[str]
    non_html_api: Pattern[str]
    language_segment: Pattern[str]
    max_url_length: int
    prefer_https: bool
    strip_www: bool
    pagination_hints: Set[str]
    max_pagination_page: int


def load_patterns() -> ParsingPatterns:
    cfg = get_parsing_config()

    html_ct = re.compile("(" + "|".join(map(re.escape, cfg.html_content_types)) + ")", re.I)
    sitemap_ct = re.compile("(" + "|".join(map(re.escape, cfg.sitemap_content_types)) + ")", re.I)
    url_in_text = re.compile(cfg.url_in_text_pattern, re.I)

    asset_extensions = {e.lower().lstrip(".") for e in cfg.asset_extensions}

    non_html_join = "|".join(re.escape(s) for s in cfg.non_html_api_patterns)
    non_html_api = re.compile(non_html_join, re.I)

    language_segment = re.compile(cfg.language_segment_pattern, re.I)

    pagination_hints = {p.lower() for p in cfg.pagination_hints}

    return ParsingPatterns(
        html_ct=html_ct,
        sitemap_ct=sitemap_ct,
        url_in_text=url_in_text,
        asset_extensions=asset_extensions,
        non_html_api=non_html_api,
        language_segment=language_segment,
        max_url_length=cfg.max_url_length,
        prefer_https=cfg.prefer_https,
        strip_www=cfg.strip_www,
        pagination_hints=pagination_hints,
        max_pagination_page=cfg.max_pagination_page,
    )
