import pkgutil
import importlib
import inspect
from typing import Dict, Type

from app.docling.exporters.base import BaseExporter

EXPORTER_MAP: Dict[str, Type[BaseExporter]] = {}


def discover_exporters():
    """Auto-discover all exporters in this package and register them."""
    global EXPORTER_MAP

    package = __name__
    for _, module_name, _ in pkgutil.iter_modules(__path__):
        if module_name == "base":
            continue

        module = importlib.import_module(f"{package}.{module_name}")

        for _, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, BaseExporter) and obj is not BaseExporter:
                for fmt in obj.supported_formats():
                    EXPORTER_MAP[fmt.lower()] = obj


discover_exporters()
