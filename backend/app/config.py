
import warnings

from pydantic_settings import BaseSettings


_INSECURE_DEFAULTS = {
    "SECRET_KEY": ("change-this-secret-key", "mindpilot-secret-change-me"),
    "API_KEY": ("change-this-api-key",),
}


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # App
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    APP_NAME: str = "MindPilot"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "production"

    # API Keys
    ZHIPU_API_KEY: str = ""
    CLAUDE_API_KEY: str = ""

    # MySQL
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "mindpilot"
    MYSQL_PASSWORD: str = ""
    MYSQL_DATABASE: str = "mindpilot"

    @property
    def MYSQL_URL(self) -> str:
        return (
            f"mysql+aiomysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
        )

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str | None = None

    @property
    def REDIS_URL(self) -> str:
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}"

    # Milvus
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530
    VECTOR_STORE: str = "milvus"  # "milvus" or "faiss"

    # Security
    SECRET_KEY: str = ""
    API_KEY: str = ""
    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Upload limits
    MAX_UPLOAD_SIZE_MB: int = 50

    # RAG
    EMBEDDING_DIM: int = 2048
    EMBEDDING_MODEL: str = "embedding-3"
    LLM_MODEL: str = "glm-4-flash"
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 100
    DEFAULT_VECTOR_WEIGHT: float = 0.7
    DEFAULT_BM25_WEIGHT: float = 0.3
    MAX_ITERATIONS: int = 5
    AGENT_TIMEOUT: int = 30

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


settings = Settings()

# Startup security validation
if settings.ENVIRONMENT == "production":
    _missing = []
    if not settings.SECRET_KEY or any(
        settings.SECRET_KEY in insecure for insecure in _INSECURE_DEFAULTS["SECRET_KEY"]
    ):
        _missing.append("SECRET_KEY")
    if not settings.ZHIPU_API_KEY:
        _missing.append("ZHIPU_API_KEY")
    if _missing:
        warnings.warn(
            f"Production environment requires secure values for: {', '.join(_missing)}. "
            f"Set them via environment variables or .env file.",
            stacklevel=2,
        )
