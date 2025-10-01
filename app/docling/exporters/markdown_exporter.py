from pathlib import Path
from typing import Any

from app.docling.exporters.base import BaseExporter


class MarkdownExporter(BaseExporter):
    @classmethod
    def supported_formats(cls) -> list[str]:
        return ["md", "markdown"]

    def export(self, doc: Any, name: str, output_dir: Path) -> Path:
        out_path = output_dir / f"{name}.md"
        out_path.write_text(doc.export_to_markdown(), encoding="utf-8")
        return out_path
