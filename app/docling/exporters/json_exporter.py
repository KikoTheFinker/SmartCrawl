import json
from pathlib import Path
from typing import Any

from app.docling.exporters.base import BaseExporter


class JsonExporter(BaseExporter):
    @classmethod
    def supported_formats(cls) -> list[str]:
        return ["json"]

    def export(self, doc: Any, name: str, output_dir: Path) -> Path:
        out_path = output_dir / f"{name}.json"
        out_path.write_text(
            json.dumps(doc.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        return out_path
