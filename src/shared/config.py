"""Configuration management using pydantic-settings."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # API Gateway
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)

    # Redis
    redis_host: str = Field(default="localhost")
    redis_port: int = Field(default=6379)
    redis_db: int = Field(default=0)

    # PostgreSQL
    postgres_host: str = Field(default="localhost")
    postgres_port: int = Field(default=5432)
    postgres_user: str = Field(default="postgres")
    postgres_password: str = Field(default="postgres")
    postgres_db: str = Field(default="mtai_platform")

    # Rate Limits (requests per minute)
    rate_limit_gold: int = Field(default=1000)
    rate_limit_silver: int = Field(default=100)
    rate_limit_bronze: int = Field(default=10)

    # Queue Names
    queue_gold: str = Field(default="gold_queue")
    queue_silver: str = Field(default="silver_queue")
    queue_bronze: str = Field(default="bronze_queue")

    # Scaling Thresholds
    scale_up_threshold: int = Field(default=10)
    scale_down_threshold: int = Field(default=2)
    scale_down_idle_minutes: int = Field(default=5)

    # vLLM Configuration
    vllm_model_name: str = Field(default="TinyLlama/TinyLlama-1.1B-Chat-v1.0")
    vllm_base_url: str = Field(default="http://localhost:8000")

    # Kubernetes
    k8s_namespace: str = Field(default="default")
    k8s_in_cluster: bool = Field(default=False)

    @property
    def database_url(self) -> str:
        """Construct PostgreSQL connection URL."""
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        """Construct Redis connection URL."""
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"


# Global settings instance
settings = Settings()
