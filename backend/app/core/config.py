from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BACKEND_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "IT资产全生命周期管理系统"
    api_prefix: str = "/api"

    database_url: str = f"sqlite:///{(DATA_DIR / 'asset.db').as_posix()}"

    jwt_secret: str = "dev-secret-change-me-in-production-at-least-32-bytes"
    jwt_alg: str = "HS256"
    token_expire_minutes: int = 720

    frontend_url: str = "http://localhost:5173"

    reminder_enabled: bool = True
    reminder_hour: int = 9

    smtp_host: str = ""
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""


settings = Settings()
