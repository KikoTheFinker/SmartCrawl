from pathlib import Path
from typing import Any


class BaseExporter:
    @classmethod
    def supported_formats(cls) -> list[str]:
        raise NotImplementedError

    def export(self, doc: Any, name: str, output_dir: Path) -> Path:
        raise NotImplementedError
