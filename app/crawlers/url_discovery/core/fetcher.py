from typing import Optional

import httpx


class HtmlFetcher:
    def __init__(self, client: httpx.AsyncClient, patterns, logger):
        self.client = client
        self.patterns = patterns
        self.logger = logger

    async def fetch_html(self, url: str, verbose: bool = False) -> Optional[str]:
        try:
            if verbose:
                self.logger.info(f"GET {url}")
            r = await self.client.get(url, follow_redirects=True)
            ctype = r.headers.get("content-type", "") or ""
            if verbose:
                self.logger.info(f"{r.status_code} {url} [{ctype}]")
            if self.patterns.html_ct.search(ctype):
                return r.text
            return None
        except httpx.RequestError as e:
            if verbose:
                self.logger.warning(f"HTTP error at {url}: {e}")
            return None
        except httpx.TimeoutException as e:
            if verbose:
                self.logger.warning(f"Timeout fetching {url}: {e}")
            return None
