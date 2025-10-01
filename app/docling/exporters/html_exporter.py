from pathlib import Path
from typing import Any

from app.docling.exporters.base import BaseExporter


class HtmlExporter(BaseExporter):
    @classmethod
    def supported_formats(cls) -> list[str]:
        return ["html"]

    def export(self, doc: Any, name: str, output_dir: Path) -> Path:
        out_path = output_dir / f"{name}.html"
        out_path.write_text(doc.export_to_html(), encoding="utf-8")
        return out_path
