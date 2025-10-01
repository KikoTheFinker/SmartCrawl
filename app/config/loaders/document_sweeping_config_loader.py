from app.config.loaders.env_loader import env_settings
from app.config.loaders.helpers.yaml_loading_helper import load_yaml
from app.config.models.app_config_model import DocumentSweepingConfig


def get_document_sweeping_config() -> DocumentSweepingConfig:
    data = load_yaml(env_settings.get_config_path())
    cfg = data.get("document_sweeping", {})
    return DocumentSweepingConfig(**cfg)


