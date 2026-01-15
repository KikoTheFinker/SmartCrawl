"""
Playwright-based HTML fetcher for JavaScript-rendered pages.

Use this when sites load content dynamically via JavaScript.
"""

from typing import Optional
from playwright.async_api import async_playwright, Browser, BrowserContext


class PlaywrightHtmlFetcher:
    """Fetches fully-rendered HTML using Playwright (headless browser)."""
    
    def __init__(
        self,
        timeout: int = 30000,
        scroll_page: bool = True,
        wait_for_idle: bool = True,
        logger=None,
    ):
        self.timeout = timeout
        self.scroll_page = scroll_page
        self.wait_for_idle = wait_for_idle
        self.logger = logger
        
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
    
    async def start(self):
        """Initialize Playwright browser."""
        if self._browser is None:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=True)
            self._context = await self._browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
            )
            if self.logger:
                self.logger.info("Playwright browser started")
    
    async def close(self):
        """Close Playwright browser."""
        if self._context:
            await self._context.close()
            self._context = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
            if self.logger:
                self.logger.info("Playwright browser closed")
    
    async def fetch_html(self, url: str, verbose: bool = False) -> Optional[str]:
        """
        Fetch fully-rendered HTML from URL using Playwright.
        
        This executes JavaScript and waits for dynamic content to load.
        """
        if self._context is None:
            await self.start()
        
        page = None
        try:
            if verbose and self.logger:
                self.logger.info(f"[Playwright] GET {url}")
            
            page = await self._context.new_page()
            
            # Navigate to page
            wait_until = "networkidle" if self.wait_for_idle else "domcontentloaded"
            response = await page.goto(url, wait_until=wait_until, timeout=self.timeout)
            
            if response is None or response.status >= 400:
                if verbose and self.logger:
                    status = response.status if response else "no response"
                    self.logger.warning(f"[Playwright] Failed {url}: {status}")
                return None
            
            # Scroll to trigger lazy loading
            if self.scroll_page:
                await self._scroll_page(page)
            
            # Get the fully rendered HTML
            html = await page.content()
            
            if verbose and self.logger:
                self.logger.info(f"[Playwright] 200 {url} [rendered, {len(html)} bytes]")
            
            return html
            
        except Exception as e:
            if verbose and self.logger:
                self.logger.warning(f"[Playwright] Error fetching {url}: {e}")
            return None
        finally:
            if page:
                await page.close()
    
    async def _scroll_page(self, page, scroll_rounds: int = 3, delay: int = 500):
        """Scroll page to trigger lazy-loaded content."""
        for _ in range(scroll_rounds):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(delay)
        # Scroll back to top
        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(200)
