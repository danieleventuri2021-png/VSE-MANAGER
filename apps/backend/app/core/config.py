from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    db_schema: str = "gestione_vse"
    backend_host: str = "127.0.0.1"
    backend_port: int = 8000
    frontend_origin: str = "http://localhost:5173"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    data_root: Path = Path("../../data")
    input_dir: Path = Path("../../data/input")
    output_dir: Path = Path("../../data/output")
    backup_dir: Path = Path("../../data/backup")
    template_dir: Path = Path("../../data/templates")
    app_env: str = "development"
    log_level: str = "INFO"
    db_pool_size: int = 20
    db_max_overflow: int = 10
    db_pool_recycle: int = 3600
    db_pool_timeout: int = 30
    auth_secret_key: str = "cambia-questa-chiave-vse-manager"
    auth_token_expire_minutes: int = 720
    admin_username: str = "admin"
    admin_password: str = "admin"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
