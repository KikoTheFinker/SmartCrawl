from app.config.loaders.env_loader import env_settings
from app.config.loaders.helpers.yaml_loading_helper import load_yaml
from app.config.models.app_config_model import HtmlSavingConfig


def get_html_saving_config() -> HtmlSavingConfig:
    data = load_yaml(env_settings.get_config_path())
    cfg = data.get("html_saving", {})
    return HtmlSavingConfig(**cfg)
