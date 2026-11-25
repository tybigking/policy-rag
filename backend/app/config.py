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

    # 阶段 3：Embedding 与向量索引
    # provider=mock 用于离线开发和测试（确定性向量）；provider=openai 使用
    # OpenAI 兼容的 /embeddings 接口。两者输出维度都必须等于 embedding_dim。
    embedding_provider: str = "mock"
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 384
    embedding_api_key: str = ""
    embedding_base_url: str = "https://api.openai.com/v1"
    embedding_batch_size: int = 32
    embedding_timeout_seconds: int = 30

    # 阶段 4：检索与混合排序
    vector_top_k: int = 10
    keyword_top_k: int = 10
    rrf_k: int = 60
    answer_context_top_k: int = 4

    # 阶段 6：回答模型与降级
    # provider=mock 时直接走提取式降级，不调用任何外部模型；provider=openai
    # 使用 OpenAI 兼容的 /chat/completions 接口。
    llm_provider: str = "mock"
    llm_model: str = "gpt-4o-mini"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_timeout_seconds: int = 30
    strict_answer_refusal: bool = True
    extractive_fallback_enabled: bool = True

    # 阶段 7：前端静态资源与跨域
    frontend_dir: str = "../frontend"
    cors_origins: str = "*"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()