from pydantic_settings import BaseSettings


def normalize_database_url(url: str) -> str:
    """
    Convert Railway's postgres:// URL to postgresql+asyncpg:// format
    Railway provides postgres:// but SQLAlchemy with asyncpg needs postgresql+asyncpg://
    """
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    # Already in correct format or custom format
    return url


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/valley"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    class Config:
        env_file = ".env"
        extra = "ignore"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Normalize database URL for Railway compatibility
        self.database_url = normalize_database_url(self.database_url)


settings = Settings()
