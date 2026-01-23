"""
HTML Content Processor using Trafilatura and BeautifulSoup.

Extracts clean, chunk-ready text content from raw HTML.
Two modes:
- "main_content" (default): Uses Trafilatura to extract only article content
- "full_text": Uses BeautifulSoup to extract ALL visible text
"""

import hashlib
import os
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

import trafilatura
from trafilatura.settings import use_config
from bs4 import BeautifulSoup


@dataclass
class ProcessedContent:
    """Container for processed HTML content."""
    url: str
    raw_html: str
    clean_text: str
    title: Optional[str] = None
    description: Optional[str] = None
    author: Optional[str] = None
    date: Optional[str] = None


@dataclass
class SiteCommonContent:
    """Container for common site elements (header, footer, sidebar)."""
    domain: str
    header_text: Optional[str] = None
    footer_text: Optional[str] = None
    sidebar_text: Optional[str] = None
    navigation_links: Optional[list] = None


def get_trafilatura_config():
    """Get optimized trafilatura config for content extraction."""
    config = use_config()
    config.set("DEFAULT", "EXTRACTION_TIMEOUT", "30")
    config.set("DEFAULT", "MIN_OUTPUT_SIZE", "50")
    config.set("DEFAULT", "MIN_EXTRACTED_SIZE", "20")
    return config


def _extract_text_with_links(soup, base_url: str) -> str:
    """
    Extract text from BeautifulSoup object, preserving links with their hrefs.
    
    Format: "Link Text [URL]" for each link found.
    """
    from urllib.parse import urljoin
    
    # Create a copy to avoid modifying the original
    soup_copy = BeautifulSoup(str(soup), "lxml")
    
    # Find all links and replace them with formatted text
    for link in soup_copy.find_all('a', href=True):
        href = link.get('href', '').strip()
        link_text = link.get_text(strip=True)
        
        # Skip empty links or javascript/mailto links
        if not href or href.startswith(('javascript:', 'mailto:', '#')):
            # Keep just the text
            link.replace_with(link_text if link_text else '')
            continue
        
        # Resolve relative URLs
        if href.startswith(('http://', 'https://')):
            full_url = href
        else:
            full_url = urljoin(base_url, href)
        
        # Replace link with formatted text: "Link Text [URL]"
        if link_text:
            link.replace_with(f"{link_text} [{full_url}]")
        else:
            # Link with no text, just show URL
            link.replace_with(f"[{full_url}]")
    
    # Now extract text normally (links are already formatted)
    text = soup_copy.get_text(separator="\n", strip=True)
    
    return text


def extract_site_common_elements(html: str, domain: str) -> SiteCommonContent:
    """
    Extract common site elements (header, footer, sidebar) that are typically
    duplicated across all pages.
    
    Returns a SiteCommonContent object with the extracted text.
    """
    if not html or not html.strip():
        return SiteCommonContent(domain=domain)
    
    soup = BeautifulSoup(html, "lxml")
    
    # Remove scripts and styles first
    for element in soup(["script", "style", "noscript"]):
        element.decompose()
    
    # Extract header content
    header_text = None
    header_selectors = [
        "header",
        "[role='banner']",
        ".site-header",
        "#header",
        "#masthead",
    ]
    for selector in header_selectors:
        header_elem = soup.select_one(selector)
        if header_elem:
            header_text = header_elem.get_text(separator="\n", strip=True)
            header_text = re.sub(r'\n{3,}', '\n\n', header_text)
            break
    
    # Extract navigation links from header
    nav_links = []
    nav_selectors = ["nav", "[role='navigation']", ".navigation", ".menu", "#menu"]
    for selector in nav_selectors:
        nav_elem = soup.select_one(selector)
        if nav_elem:
            for link in nav_elem.find_all("a", href=True):
                link_text = link.get_text(strip=True)
                link_href = link.get("href", "")
                if link_text and link_href:
                    nav_links.append({"text": link_text, "href": link_href})
            break
    
    # Extract footer content
    footer_text = None
    footer_selectors = [
        "footer",
        "[role='contentinfo']",
        ".site-footer",
        "#footer",
        "#colophon",
    ]
    for selector in footer_selectors:
        footer_elem = soup.select_one(selector)
        if footer_elem:
            footer_text = footer_elem.get_text(separator="\n", strip=True)
            footer_text = re.sub(r'\n{3,}', '\n\n', footer_text)
            break
    
    # Extract sidebar content
    sidebar_text = None
    sidebar_selectors = [
        "aside",
        "[role='complementary']",
        ".sidebar",
        "#sidebar",
        "#secondary",
    ]
    for selector in sidebar_selectors:
        sidebar_elem = soup.select_one(selector)
        if sidebar_elem:
            sidebar_text = sidebar_elem.get_text(separator="\n", strip=True)
            sidebar_text = re.sub(r'\n{3,}', '\n\n', sidebar_text)
            break
    
    return SiteCommonContent(
        domain=domain,
        header_text=header_text if header_text and len(header_text) > 10 else None,
        footer_text=footer_text if footer_text and len(footer_text) > 10 else None,
        sidebar_text=sidebar_text if sidebar_text and len(sidebar_text) > 10 else None,
        navigation_links=nav_links if nav_links else None,
    )


def extract_full_text(html: str, url: str, include_links: bool = True) -> Optional[ProcessedContent]:
    """
    Extract visible text from HTML using BeautifulSoup.
    
    Removes headers, footers, navigation, and other boilerplate elements
    that are duplicated across pages.
    
    Args:
        html: Raw HTML content
        url: Source URL (for resolving relative links)
        include_links: If True, include links as "Link Text [URL]"
    """
    import json
    
    if not html or not html.strip():
        return None
    
    # First, try to extract JSON-LD data before removing scripts
    jsonld_author = None
    jsonld_date = None
    soup_for_jsonld = BeautifulSoup(html, "lxml")
    for script in soup_for_jsonld.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            # Handle @graph structure
            items = data.get("@graph", [data]) if isinstance(data, dict) else [data]
            for item in items:
                if not isinstance(item, dict):
                    continue
                # Get author
                if not jsonld_author:
                    author_data = item.get("author")
                    if isinstance(author_data, dict):
                        jsonld_author = author_data.get("name")
                    elif isinstance(author_data, str):
                        jsonld_author = author_data
                # Get date
                if not jsonld_date:
                    jsonld_date = item.get("datePublished") or item.get("dateModified")
        except (json.JSONDecodeError, TypeError):
            continue
    
    soup = BeautifulSoup(html, "lxml")
    
    # Extract metadata BEFORE removing head section
    # Get title
    title = None
    title_tag = soup.find("title")
    if title_tag:
        title = title_tag.get_text(strip=True)
    # Try og:title as fallback
    if not title:
        og_title = soup.find("meta", property="og:title")
        if og_title:
            title = og_title.get("content", "").strip()
    
    # Get meta description
    description = None
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc:
        description = meta_desc.get("content", "").strip()
    # Try og:description as fallback
    if not description:
        og_desc = soup.find("meta", property="og:description")
        if og_desc:
            description = og_desc.get("content", "").strip()
    
    # Get author from various sources (fallback if JSON-LD didn't have it)
    author = jsonld_author
    if not author:
        # Try meta author
        meta_author = soup.find("meta", attrs={"name": "author"})
        if meta_author:
            author = meta_author.get("content", "").strip()
    if not author:
        # Try article:author
        article_author = soup.find("meta", property="article:author")
        if article_author:
            author = article_author.get("content", "").strip()
    if not author:
        # Try schema.org author
        schema_author = soup.find("span", itemprop="author")
        if schema_author:
            author = schema_author.get_text(strip=True)
    if not author:
        # Try common author class names
        for class_name in ["author", "byline", "post-author", "entry-author"]:
            author_elem = soup.find(class_=class_name)
            if author_elem:
                author = author_elem.get_text(strip=True)
                break
    
    # Get date from various sources (fallback if JSON-LD didn't have it)
    date = jsonld_date
    if not date:
        # Try article:published_time
        pub_time = soup.find("meta", property="article:published_time")
        if pub_time:
            date = pub_time.get("content", "").strip()
    if not date:
        # Try article:modified_time as fallback
        mod_time = soup.find("meta", property="article:modified_time")
        if mod_time:
            date = mod_time.get("content", "").strip()
    if not date:
        # Try datePublished schema.org
        date_elem = soup.find(itemprop="datePublished")
        if date_elem:
            date = date_elem.get("content") or date_elem.get("datetime") or date_elem.get_text(strip=True)
    if not date:
        # Try time tag
        time_tag = soup.find("time")
        if time_tag:
            date = time_tag.get("datetime") or time_tag.get_text(strip=True)
    
    # Try to find main content area FIRST (before removing anything)
    # This ensures we preserve the main content even if it's nested
    main_content = None
    
    # Priority 1: Most specific content selectors (usually contain the actual article content)
    priority_selectors = [
        ".post-content",
        ".entry-content",
        "article .post-content",
        "article .entry-content",
        "#content .post-content",
        "#content .entry-content",
    ]
    
    for selector in priority_selectors:
        main_elem = soup.select_one(selector)
        if main_elem:
            text_len = len(main_elem.get_text(strip=True))
            if text_len > 50:  # Has substantial content
                main_content = main_elem
                break
    
    # Priority 2: Main content containers
    if not main_content:
        main_selectors = [
            "main",
            "article",
            "[role='main']",
            "#content",
            "#main-content",
            ".page-content",
            ".main-content",
        ]
        
        for selector in main_selectors:
            main_elem = soup.select_one(selector)
            if main_elem:
                text_len = len(main_elem.get_text(strip=True))
                if text_len > 100:  # Has substantial content
                    main_content = main_elem
                    break
    
    # Priority 3: Broader selectors (last resort)
    if not main_content:
        for selector in [".content", "[class*='content']"]:
            main_elem = soup.select_one(selector)
            if main_elem:
                # Check if it has substantial content (not just a wrapper)
                text_len = len(main_elem.get_text(strip=True))
                if text_len > 200:  # Needs more content to avoid false positives
                    main_content = main_elem
                    break
    
    # NOW remove head section (after extracting metadata and finding main content)
    head = soup.find("head")
    if head:
        head.decompose()
    
    # Remove script, style, and non-content elements
    for element in soup(["script", "style", "noscript", "iframe", "svg"]):
        element.decompose()
    
    # If we found main content, clean it up by removing nested boilerplate
    if main_content:
        # Remove nested navigation/header/footer from main content
        for nested_nav in main_content.select("nav, header, footer, aside, .menu, .navigation, .breadcrumb, .breadcrumbs"):
            nested_nav.decompose()
        # Remove nested scripts/styles that might have been missed
        for nested_script in main_content.select("script, style, noscript"):
            nested_script.decompose()
    else:
        # No main content found, remove header/footer/sidebar from whole page
        # Remove header elements (navigation, site header, etc.)
        header_selectors = [
            "header",
            "nav", 
            "[role='banner']",
            "[role='navigation']",
            ".header",
            ".site-header",
            ".page-header",
            ".navbar",
            ".nav",
            ".navigation",
            ".menu",
            ".top-bar",
            "#header",
            "#nav",
            "#navigation",
            "#menu",
            "#masthead",
        ]
        for selector in header_selectors:
            for element in soup.select(selector):
                element.decompose()
        
        # Remove footer elements
        footer_selectors = [
            "footer",
            "[role='contentinfo']",
            ".footer",
            ".site-footer",
            ".page-footer",
            "#footer",
            "#colophon",
            ".copyright",
            ".bottom-bar",
        ]
        for selector in footer_selectors:
            for element in soup.select(selector):
                element.decompose()
        
        # Remove sidebar elements
        sidebar_selectors = [
            "aside",
            "[role='complementary']",
            ".sidebar",
            ".widget-area",
            ".side-bar",
            "#sidebar",
            "#secondary",
        ]
        for selector in sidebar_selectors:
            for element in soup.select(selector):
                element.decompose()
        
        # Remove common non-content elements
        other_selectors = [
            ".breadcrumb",
            ".breadcrumbs",
            ".social-share",
            ".share-buttons",
            ".related-posts",
            ".comments",
            "#comments",
            ".advertisement",
            ".ad",
            ".ads",
            "[class*='cookie']",
            "[class*='popup']",
            "[class*='modal']",
            ".skip-link",
            ".screen-reader-text",
        ]
        for selector in other_selectors:
            for element in soup.select(selector):
                element.decompose()
    
    # Extract text from main content area if found, otherwise from whole page
    if main_content:
        if include_links:
            # Extract text with links
            text_parts = []
            for elem in main_content.find_all(text=True):
                parent = elem.parent
                if parent and parent.name == 'a':
                    href = parent.get('href', '')
                    link_text = elem.strip()
                    if link_text:
                        text_parts.append(f"{link_text} [{href}]")
                elif elem.strip():
                    text_parts.append(elem.strip())
            text = "\n".join(text_parts)
        else:
            text = main_content.get_text(separator="\n", strip=True)
    else:
        # Fallback: extract from whole page (already had header/footer/sidebar removed)
        if include_links:
            # Extract text with links
            text_parts = []
            for elem in soup.find_all(text=True):
                parent = elem.parent
                if parent and parent.name == 'a':
                    href = parent.get('href', '')
                    link_text = elem.strip()
                    if link_text:
                        text_parts.append(f"{link_text} [{href}]")
                elif elem.strip():
                    text_parts.append(elem.strip())
            text = "\n".join(text_parts)
        else:
            text = soup.get_text(separator="\n", strip=True)
    
    # Clean up multiple newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()
    
    # Remove title from text if it appears at the start (to avoid duplication)
    # The title is already stored separately in metadata
    if title and text.startswith(title):
        # Remove title and any following whitespace/newlines
        text = text[len(title):].strip()
        # Remove leading dashes or separators that might follow the title
        text = re.sub(r'^[–—\-–\s]+', '', text)
    
    # Final validation: ensure we have substantial content (not just title)
    if not text or len(text.strip()) < 50:
        return None
    
    # Additional check: if text is too similar to just the title, it's probably not valid content
    if title and len(text.strip()) < len(title) * 1.5:
        # Text is too short compared to title, likely just extracted title
        return None
    
    return ProcessedContent(
        url=url,
        raw_html=html,
        clean_text=text.strip(),
        title=title,
        description=description,
        author=author if author else None,
        date=date if date else None,
    )


def extract_clean_content(
    html: str,
    url: str,
    include_tables: bool = True,
    include_links: bool = False,
    include_images: bool = False,
    output_format: str = "txt",
    extraction_mode: str = "main_content",
) -> Optional[ProcessedContent]:
    """
    Extract text content from HTML.
    
    Args:
        html: Raw HTML content
        url: Source URL (used for metadata)
        include_tables: Whether to preserve table content
        include_links: Whether to preserve hyperlinks
        include_images: Whether to include image references
        output_format: Output format - 'txt', 'markdown', or 'xml'
        extraction_mode: "main_content" (Trafilatura) or "full_text" (BeautifulSoup)
    
    Returns:
        ProcessedContent with cleaned text, or None if extraction fails
    """
    if not html or not html.strip():
        return None
    
    # Use full text extraction if requested
    if extraction_mode == "full_text":
        return extract_full_text(html, url, include_links=include_links)
    
    # Use Trafilatura for main content extraction
    config = get_trafilatura_config()
    
    # Extract main content
    clean_text = trafilatura.extract(
        html,
        url=url,
        include_tables=include_tables,
        include_links=include_links,
        include_images=include_images,
        include_comments=False,
        output_format=output_format,
        config=config,
    )
    
    if not clean_text or len(clean_text.strip()) < 50:
        # Fallback to full text if main content extraction fails
        return extract_full_text(html, url, include_links=include_links)
    
    # Extract metadata
    metadata = trafilatura.extract_metadata(html, default_url=url)
    
    return ProcessedContent(
        url=url,
        raw_html=html,
        clean_text=clean_text.strip(),
        title=metadata.title if metadata else None,
        description=metadata.description if metadata else None,
        author=metadata.author if metadata else None,
        date=metadata.date if metadata else None,
    )


def url_to_filename(url: str, extension: str = "txt") -> str:
    """Convert URL to a safe filename."""
    parsed = urlparse(url)
    
    # Create base from path
    path = parsed.path.strip("/").replace("/", "_") or "index"
    
    # Add query hash if present
    if parsed.query:
        query_hash = hashlib.md5(parsed.query.encode()).hexdigest()[:8]
        path = f"{path}_{query_hash}"
    
    # Sanitize filename
    path = re.sub(r'[<>:"/\\|?*]', '_', path)
    path = re.sub(r'_+', '_', path)
    path = path[:200]  # Limit length
    
    return f"{path}.{extension}"


class HtmlContentSaver:
    """Saves raw HTML and processed content to disk."""
    
    def __init__(
        self,
        output_dir: str,
        save_raw: bool = True,
        save_processed: bool = True,
        output_format: str = "txt",
        include_tables: bool = True,
        include_links: bool = False,
        extraction_mode: str = "full_text",  # "main_content" or "full_text"
    ):
        self.output_dir = output_dir
        self.save_raw = save_raw
        self.save_processed = save_processed
        self.output_format = output_format
        self.include_tables = include_tables
        self.include_links = include_links
        self.extraction_mode = extraction_mode
        
        self.raw_dir = os.path.join(output_dir, "raw_html")
        self.processed_dir = os.path.join(output_dir, "processed")
        self.metadata_dir = os.path.join(output_dir, "metadata")
        self.common_dir = os.path.join(output_dir, "site_common")
        
        # Track which domains we've already saved common content for
        self._saved_common_domains: set = set()
        
        # Create directories
        if save_raw:
            os.makedirs(self.raw_dir, exist_ok=True)
        if save_processed:
            os.makedirs(self.processed_dir, exist_ok=True)
            os.makedirs(self.metadata_dir, exist_ok=True)
            os.makedirs(self.common_dir, exist_ok=True)
    
    def save(self, url: str, html: str, logger=None) -> Optional[ProcessedContent]:
        """
        Save raw HTML and extract/save processed content.
        
        Returns ProcessedContent if extraction succeeds, None otherwise.
        """
        parsed = urlparse(url)
        domain = parsed.netloc
        domain_prefix = domain.replace(".", "_").replace(":", "_")
        
        # Save common site elements (header/footer/sidebar) once per domain
        if domain not in self._saved_common_domains and self.save_processed:
            self._save_site_common(html, domain, domain_prefix, logger)
            self._saved_common_domains.add(domain)
        
        # Save raw HTML
        if self.save_raw:
            raw_filename = f"{domain_prefix}_{url_to_filename(url, 'html')}"
            raw_path = os.path.join(self.raw_dir, raw_filename)
            try:
                with open(raw_path, "w", encoding="utf-8") as f:
                    f.write(html)
                if logger:
                    logger.debug(f"Saved raw HTML: {raw_path}")
            except OSError as e:
                if logger:
                    logger.warning(f"Failed to save raw HTML for {url}: {e}")
        
        # Extract and save processed content
        if self.save_processed:
            processed = extract_clean_content(
                html=html,
                url=url,
                include_tables=self.include_tables,
                include_links=self.include_links,
                output_format=self.output_format,
                extraction_mode=self.extraction_mode,
            )
            
            if processed and processed.clean_text:
                ext = "md" if self.output_format == "markdown" else "txt"
                processed_filename = f"{domain_prefix}_{url_to_filename(url, ext)}"
                processed_path = os.path.join(self.processed_dir, processed_filename)
                
                try:
                    with open(processed_path, "w", encoding="utf-8") as f:
                        f.write(processed.clean_text)
                    if logger:
                        logger.debug(f"Saved processed content: {processed_path}")
                    
                    # Save metadata as JSON (includes reference to common content)
                    self._save_metadata(url, processed, domain_prefix, logger)
                    
                    return processed
                except OSError as e:
                    if logger:
                        logger.warning(f"Failed to save processed content for {url}: {e}")
        
        return None
    
    def _save_site_common(self, html: str, domain: str, domain_prefix: str, logger=None):
        """Extract and save common site elements (header, footer, sidebar)."""
        import json
        
        common = extract_site_common_elements(html, domain)
        
        # Save header
        if common.header_text:
            header_path = os.path.join(self.common_dir, f"{domain_prefix}_header.txt")
            try:
                with open(header_path, "w", encoding="utf-8") as f:
                    f.write(common.header_text)
                if logger:
                    logger.info(f"Saved site header: {header_path}")
            except OSError as e:
                if logger:
                    logger.warning(f"Failed to save header for {domain}: {e}")
        
        # Save footer
        if common.footer_text:
            footer_path = os.path.join(self.common_dir, f"{domain_prefix}_footer.txt")
            try:
                with open(footer_path, "w", encoding="utf-8") as f:
                    f.write(common.footer_text)
                if logger:
                    logger.info(f"Saved site footer: {footer_path}")
            except OSError as e:
                if logger:
                    logger.warning(f"Failed to save footer for {domain}: {e}")
        
        # Save sidebar
        if common.sidebar_text:
            sidebar_path = os.path.join(self.common_dir, f"{domain_prefix}_sidebar.txt")
            try:
                with open(sidebar_path, "w", encoding="utf-8") as f:
                    f.write(common.sidebar_text)
                if logger:
                    logger.info(f"Saved site sidebar: {sidebar_path}")
            except OSError as e:
                if logger:
                    logger.warning(f"Failed to save sidebar for {domain}: {e}")
        
        # Save metadata for common content
        meta_path = os.path.join(self.common_dir, f"{domain_prefix}_metadata.json")
        metadata = {
            "domain": domain,
            "has_header": common.header_text is not None,
            "has_footer": common.footer_text is not None,
            "has_sidebar": common.sidebar_text is not None,
            "header_length": len(common.header_text) if common.header_text else 0,
            "footer_length": len(common.footer_text) if common.footer_text else 0,
            "sidebar_length": len(common.sidebar_text) if common.sidebar_text else 0,
            "navigation_links": common.navigation_links,
        }
        try:
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            if logger:
                logger.info(f"Saved site common metadata: {meta_path}")
        except OSError as e:
            if logger:
                logger.warning(f"Failed to save common metadata for {domain}: {e}")
    
    def _save_metadata(self, url: str, content: ProcessedContent, domain_prefix: str, logger=None):
        """Save metadata as JSON."""
        import json
        
        meta_filename = f"{domain_prefix}_{url_to_filename(url, 'json')}"
        meta_path = os.path.join(self.metadata_dir, meta_filename)
        
        metadata = {
            "url": url,
            "title": content.title,
            "description": content.description,
            "author": content.author,
            "date": content.date,
            "content_length": len(content.clean_text),
            # Reference to common site content
            "site_common": {
                "header_file": f"site_common/{domain_prefix}_header.txt",
                "footer_file": f"site_common/{domain_prefix}_footer.txt",
                "sidebar_file": f"site_common/{domain_prefix}_sidebar.txt",
                "metadata_file": f"site_common/{domain_prefix}_metadata.json",
            }
        }
        
        try:
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
        except OSError as e:
            if logger:
                logger.debug(f"Failed to save metadata for {url}: {e}")
