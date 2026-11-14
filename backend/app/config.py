from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置：优先读 backend/.env，其次读系统环境变量。"""

    secret_key: str = "dev-only-secret-key-0123456789abcdef0123456789abcdef"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    database_url: str = "postgresql+psycopg://postgres:mysecretpassword@localhost:5432/mydb"

    # 阶段 2：文档摄取
    storage_dir: str = "storage"
    max_upload_size_bytes: int = 20 * 1024 * 1024
    chunk_size: int = 800
    chunk_overlap: int = 80

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
