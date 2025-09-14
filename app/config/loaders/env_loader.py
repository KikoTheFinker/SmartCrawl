import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class EnvSettings:
    @staticmethod
    def get_config_path() -> Path:
        config_path = os.getenv("CONFIG_PATH")
        if not config_path:
            raise EnvironmentError("CONFIG_PATH not set in .env")

        return Path(__file__).resolve().parents[3] / config_path  # root


env_settings = EnvSettings()
