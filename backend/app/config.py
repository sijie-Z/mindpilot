
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # App
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    APP_NAME: str = "MindPilot"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"

    # API Keys
    ZHIPU_API_KEY: str = ""
    CLAUDE_API_KEY: str = ""

    # MySQL
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
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
    SECRET_KEY: str = "change-this-secret-key"
    API_KEY: str = "change-this-api-key"
    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # RAG
    EMBEDDING_DIM: int = 2048
    EMBEDDING_MODEL: str = "embedding-3"
    LLM_MODEL: str = "glm-4-flash"  # 快速响应，也可用 glm-4-plus
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
