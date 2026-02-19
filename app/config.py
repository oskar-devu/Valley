import os
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_database_url(url: str) -> str:
    """
    Convert Railway's postgres:// URL to postgresql+asyncpg:// format
    Railway provides postgres:// but SQLAlchemy with asyncpg needs postgresql+asyncpg://
    """
    original_url = url
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://") and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    # Log URL info (masked for security)
    if original_url != url:
        print(f"✓ Converted database URL from {original_url.split('@')[0]}@... to {url.split('@')[0]}@...")
    else:
        # Mask the URL for logging
        masked = url.split('@')[0] + "@..." if '@' in url else url[:20] + "..."
        print(f"✓ Using database URL: {masked}")
    
    return url


class Settings(BaseSettings):
    # Pydantic Settings v2 automatically reads from environment variables
    # DATABASE_URL will be read automatically (case-insensitive)
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/valley"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Explicitly check environment variable as fallback
        # Railway sets DATABASE_URL, ensure we're using it
        env_db_url = os.getenv("DATABASE_URL")
        if env_db_url:
            print(f"✓ Found DATABASE_URL in environment variables")
            self.database_url = env_db_url
        elif self.database_url == "postgresql+asyncpg://postgres:postgres@localhost:5432/valley":
            print("⚠ WARNING: DATABASE_URL not found in environment. Using default localhost URL.")
            print("  This will fail in production. Please set DATABASE_URL in Railway.")
        
        # Normalize database URL for Railway compatibility
        # Railway provides postgres:// but we need postgresql+asyncpg://
        self.database_url = normalize_database_url(self.database_url)


settings = Settings()
