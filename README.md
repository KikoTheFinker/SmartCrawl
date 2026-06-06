# SmartCrawl

Async web crawler for discovering URLs, downloading HTML from URLs and processing and downloading documents. Processes PDFs, DOCX and other formats using Docling, exporting to Markdown/JSON/HTML for chatbot and RAG applications.

## Setup

1. **Install dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```

2. **Install Playwright browsers** (required for JavaScript page rendering):
   ```powershell
   playwright install
   ```

3. **Create a `.env` file** in the project root (if it doesn't exist):
   ```
   CONFIG_PATH=app/config/files/config.yaml
   ```

## Running the Project

### Basic Usage

Run URL discovery only:
```powershell
python scripts/run_orchestrator.py
```

Or specify a URL:
```powershell
python scripts/run_orchestrator.py https://example.com
```

### With Document Download

To also download documents (PDFs, Word docs, etc.) after discovery:
```powershell
python scripts/run_orchestrator.py --download
```

Or with a custom URL:
```powershell
python scripts/run_orchestrator.py https://example.com --download
```

**JavaScript Download Manager Support:**
The downloader automatically handles sites using JavaScript-based download managers:
- WordPress Download Manager
- Easy Digital Downloads
- Better File Download
- Any site with download buttons (not direct links)

It uses Playwright to click download buttons and capture the files. This is enabled by default.
Set `click_download_buttons: false` in `document_sweeping.yaml` to disable.

### With HTML Content Saving

Save raw HTML and processed (cleaned) content:
```powershell
python scripts/run_orchestrator.py --save-html
```

This will:
- Save raw HTML files to `html_output/raw_html/`
- Save processed text to `html_output/processed/`
- Save metadata (title, description, author, date) to `html_output/metadata/`

**Extraction modes** (set in `html_saving.yaml`):
- `extraction_mode: "full_text"` (default) - Extract ALL visible text from page
- `extraction_mode: "main_content"` - Extract only article content (removes nav/ads/boilerplate)

### With JavaScript Rendering (Dynamic Sites)

For sites that load content via JavaScript (React, Vue, Angular, etc.), use Playwright to render the full DOM:
```powershell
python scripts/run_orchestrator.py --save-html --use-playwright
```

This will:
- Use a headless Chrome browser to render pages
- Execute JavaScript and wait for dynamic content
- Scroll pages to trigger lazy loading
- Capture the fully-rendered HTML (not just the initial response)

**Note:** Playwright mode is slower but necessary for:
- Single Page Applications (SPAs)
- Sites with infinite scroll
- Content loaded via AJAX/fetch
- Lazy-loaded images and text

### With Document Processing (Docling)

Process downloaded documents into clean **Markdown** (ideal for LLMs/RAG):
```powershell
python scripts/run_orchestrator.py --process-docs
```

This will:
- Convert PDFs, DOCX, etc., from the `downloads/` directory.
- Save the result as highly-structured **Markdown** in `downloads/processed/markdown/`.
- Automatically **detect the language** of the content.

### Automatic Language Detection

Both HTML and document pipelines now automatically detect the language of the content and prefix files accordingly:
- **Format**: `{lang}_{original_filename}.md`
- **Example**: `en_about_us.md` or `mk_referenca.md`
- Detected language is also saved in the metadata JSON for HTML pages.

### Full Pipeline Command (The "Go" Command)

To crawl, render JS, save processed Markdown, download documents, and process them with Docling all in one go:
```powershell
python scripts/run_orchestrator.py https://pdfobject.com --save-html --use-playwright --download --process-docs
```

## Configuration

- **Test URL**: Edit `app/config/files/test.yaml` to change the default target URL.
- **HTML Saving**: Edit `app/config/files/html_saving.yaml`. Set `output_format: "markdown"` for MD output.
- **Document Sweeping**: Edit `app/config/files/document_sweeping.yaml`.
- **Language Detection**: Toggle `detect_language: true/false` in the respective config files.

## Output Structure

- **Downloads**: `downloads/` (Originals) & `downloads/processed/markdown/` (Processed)
- **HTML Output**: 
  - `html_output/raw_html/` (Original source)
  - `html_output/processed/` (Cleaned **Markdown/Text**)
  - `html_output/metadata/` (JSON metadata with detected language)
