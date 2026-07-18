from pathlib import Path

from pydantic_settings import BaseSettings


_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

class Settings(BaseSettings):
    database_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 8
    gemini_api_key: str
    listen_host: str = "127.0.0.1"
    listen_port: int = 8756
    uploads_dir: str = "uploads"

    model_config = {
        "env_file": _ENV_FILE,
        "env_file_encoding": "utf-8",
        # Desktop upgrades may encounter unrelated legacy keys in an existing
        # environment. Only declared settings are runtime configuration.
        "extra": "ignore",
    }


settings = Settings()
