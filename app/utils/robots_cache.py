import asyncio
from urllib import robotparser
from urllib.parse import urlparse

import httpx


class RobotsCache:
    def __init__(self, user_agent: str = "*", ttl: int = 600):
        self.user_agent = user_agent
        self.ttl = ttl
        self._cache = {}
        self._lock = asyncio.Lock()

    async def allowed(self, url: str, client: httpx.AsyncClient) -> bool:
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        async with self._lock:
            entry = self._cache.get(base)

            if not entry or (asyncio.get_event_loop().time() - entry[0]) > self.ttl:
                rp = robotparser.RobotFileParser()
                robots_url = f"{base}/robots.txt"
                try:
                    resp = await client.get(robots_url, timeout=10)
                    if resp.status_code < 400:
                        rp.parse(resp.text.splitlines())
                    else:
                        rp = None
                except (httpx.RequestError, httpx.TimeoutException):
                    rp = None

                self._cache[base] = (asyncio.get_event_loop().time(), rp)

            _, rp = self._cache[base]
            if not rp:
                return True
            return rp.can_fetch(self.user_agent, url)


robots_cache = RobotsCache()
