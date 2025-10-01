from typing import List, Tuple
import httpx
from selectolax.parser import HTMLParser
from urllib.parse import urljoin

from app.crawlers.document_downloader.utils.doc_filters import is_probably_js_rendered


async def extract_links_httpx(client: httpx.AsyncClient, url: str) -> Tuple[List[str], bool]:
    try:
        resp = await client.get(url, follow_redirects=True, timeout=25)
    except (httpx.RequestError, httpx.TimeoutException):
        return [], False

    html = resp.text
    tree = HTMLParser(html)
    links: List[str] = []
    for a in tree.css("a[href]"):
        normalized = normalize_url(str(resp.url), a.attributes.get("href"))
        if normalized:
            links.append(normalized)
    unique = list(dict.fromkeys(links))
    return unique, is_probably_js_rendered(html)


async def extract_with_playwright(context, url: str, scroll_rounds: int = 2,
                                  idle: str = "networkidle") -> Tuple[str, List[str], List[Tuple[str, str]]]:
    links: List[str] = []
    responses: List[Tuple[str, str]] = []
    page = await context.new_page()
    page.on("response", lambda resp: responses.append(
        (resp.url, (resp.headers.get("content-type") or "").split(";")[0].lower())
    ))
    await page.goto(url, wait_until=idle, timeout=45000)
    for _ in range(scroll_rounds):
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(800)
    anchors = await page.eval_on_selector_all("a[href]", "els => els.map(e => e.getAttribute('href'))")
    for href in anchors:
        normalized = normalize_url(page.url, href)
        if normalized:
            links.append(normalized)
    html = await page.content()
    await page.close()
    return html, list(dict.fromkeys(links)), responses


def normalize_url(base: str, href: str) -> str | None:
    if not href:
        return None
    href = href.strip()
    if href.startswith(("mailto:", "javascript:", "#")):
        return None
    return urljoin(base, href)
