import gzip

import brotli

from app.exceptions import SitemapDiscoveryError


def maybe_decompress(url: str, content: bytes) -> bytes:
    if content[:2] == b"\x1f\x8b":  # GZIP
        try:
            return gzip.decompress(content)
        except Exception as e:
            raise SitemapDiscoveryError(f"Gzip decompression failed for {url}: {e}")

    try:
        return brotli.decompress(content)
    except brotli.error:
        pass

    return content
