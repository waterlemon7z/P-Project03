from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    database_url: str = f"sqlite:///{BASE_DIR / 'storage' / 'backend.db'}"
    ai_base_url: str = "http://127.0.0.1:8001"
    ai_timeout_seconds: float = Field(default=60, gt=0, le=300)
    upload_dir: Path = BASE_DIR / "storage" / "uploads"
    max_upload_bytes: int = Field(default=20 * 1024 * 1024, gt=0)
    worker_poll_seconds: float = Field(default=0.5, gt=0)
