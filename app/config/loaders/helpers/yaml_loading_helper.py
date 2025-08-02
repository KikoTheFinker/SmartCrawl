from pathlib import Path
from typing import Dict, Any

import yaml

_yaml_cache: Dict[str, Dict[str, Any]] = {}


def load_yaml(path: Path) -> Dict[str, Any]:
    """
    Load and cache a YAML file.
    """
    resolved_path = str(path.resolve())
    if resolved_path in _yaml_cache:
        return _yaml_cache[resolved_path]

    if not path.exists():
        raise FileNotFoundError(f"YAML file not found: {path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = yaml.safe_load(f) or {}
            _yaml_cache[resolved_path] = content
            return content
    except yaml.YAMLError as e:
        raise ValueError(f"Failed to parse YAML file {path}: {e}")
