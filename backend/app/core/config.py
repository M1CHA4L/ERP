from functools import cached_property

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field(
        default="postgresql+psycopg://erp_user:erp_password@localhost:5432/manufacturing_erp",
        alias="DATABASE_URL",
    )
    jwt_secret_key: str = Field(default="dev-secret", alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=480, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    backend_cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        alias="BACKEND_CORS_ORIGINS",
    )
    file_storage_root: str = Field(default="./storage", alias="FILE_STORAGE_ROOT")
    backup_storage_dir: str = Field(default="./storage/backups", alias="BACKUP_STORAGE_DIR")
    backup_schedule_times: str = Field(default="09:00,12:00,18:00", alias="BACKUP_SCHEDULE_TIMES")
    backup_retention_days: int = Field(default=7, alias="BACKUP_RETENTION_DAYS")
    backup_timezone: str = Field(default="Asia/Shanghai", alias="BACKUP_TIMEZONE")
    backup_scheduler_enabled: bool = Field(default=True, alias="BACKUP_SCHEDULER_ENABLED")

    @cached_property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]


settings = Settings()
