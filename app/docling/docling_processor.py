import asyncio
from pathlib import Path
from typing import List

from docling.document_converter import DocumentConverter

from app.docling.exporters import EXPORTER_MAP


class DoclingProcessor:
    def __init__(self, input_dir: str, output_dir: str, export_format: str, concurrency: int = 2):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.concurrency = max(1, concurrency)

        export_format = export_format.lower()
        if export_format not in EXPORTER_MAP:
            raise ValueError(f"Unsupported export format: {export_format}")
        self.exporter = EXPORTER_MAP[export_format]()

        self.converter = DocumentConverter()
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def process_all(self) -> List[Path]:
        tasks = []
        for file_path in self.input_dir.glob("*"):
            if file_path.is_file():
                tasks.append(self._process_one_async(file_path))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, Path)]

    async def _process_one_async(self, file_path: Path) -> Path:
        return await asyncio.to_thread(self._process_one, file_path)

    def _process_one(self, file_path: Path) -> Path:
        res = self.converter.convert(str(file_path))
        doc = res.document
        return self.exporter.export(doc, file_path.stem, self.output_dir)
