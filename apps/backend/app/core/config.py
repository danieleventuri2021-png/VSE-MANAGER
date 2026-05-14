from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:Daniele@localhost:5432/postgres"
    db_schema: str = "gestione_vse"
    backend_host: str = "127.0.0.1"
    backend_port: int = 8000
    frontend_origin: str = "http://localhost:5173"
    data_root: Path = Path("../../data")
    input_dir: Path = Path("../../data/input")
    output_dir: Path = Path("../../data/output")
    backup_dir: Path = Path("../../data/backup")
    template_dir: Path = Path("../../data/templates")
    app_env: str = "development"
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
