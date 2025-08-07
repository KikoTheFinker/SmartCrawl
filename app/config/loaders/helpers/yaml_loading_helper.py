from pathlib import Path
from typing import Dict, Any
import yaml

_yaml_cache: Dict[str, Dict[str, Any]] = {}

def load_yaml(path: Path) -> Dict[str, Any]:
    resolved_path = str(path.resolve())
    if resolved_path in _yaml_cache:
        return _yaml_cache[resolved_path]

    if not path.exists():
        raise FileNotFoundError(f"YAML file not found: {path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        # Handle includes
        includes = data.pop("include", [])
        if includes:
            for include_file in includes:
                include_path = path.parent / include_file
                included_data = load_yaml(include_path)
                data.update(included_data)

        _yaml_cache[resolved_path] = data
        return data

    except yaml.YAMLError as e:
        raise ValueError(f"Failed to parse YAML file {path}: {e}")
