from pydantic_settings import BaseSettings


def normalize_database_url(url: str) -> str:
    """
    Convert Railway's postgres:// URL to postgresql+asyncpg:// format
    Railway provides postgres:// but SQLAlchemy with asyncpg needs postgresql+asyncpg://
    """
    original_url = url
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    # Log URL info (masked for security)
    if original_url != url:
        print(f"Converted database URL from {original_url.split('@')[0]}@... to {url.split('@')[0]}@...")
    else:
        # Mask the URL for logging
        masked = url.split('@')[0] + "@..." if '@' in url else url[:20] + "..."
        print(f"Using database URL: {masked}")
    
    return url


class Settings(BaseSettings):
    # Pydantic Settings automatically reads from environment variables
    # DATABASE_URL will be read automatically (case-insensitive)
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/valley"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    class Config:
        env_file = ".env"
        extra = "ignore"
        # Explicitly map DATABASE_URL env var to database_url field
        env_prefix = ""
        case_sensitive = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Normalize database URL for Railway compatibility
        # Railway provides postgres:// but we need postgresql+asyncpg://
        self.database_url = normalize_database_url(self.database_url)


settings = Settings()
