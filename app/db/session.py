from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.config import settings
from app.db.base import Base

_engine = None
_session_factory = None


def get_engine():
    global _engine
    if _engine is None:
        # Railway PostgreSQL requires SSL, but asyncpg handles this automatically
        # We can add connect_args if needed, but asyncpg should detect SSL from URL
        connect_args = {}
        
        # Check if we're likely on Railway (production environment)
        import os
        if os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("DATABASE_URL"):
            # Railway PostgreSQL typically requires SSL
            # asyncpg will use SSL if the URL has ?sslmode=require or similar
            # But we can also set it explicitly if needed
            pass
        
        _engine = create_async_engine(
            settings.database_url,
            echo=False,
            pool_pre_ping=True,  # Verify connections before using them
            pool_recycle=300,  # Recycle connections after 5 minutes
            connect_args=connect_args,
        )
    return _engine


def get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """
    Initialize database - create tables if they don't exist.
    Includes retry logic for Railway deployments where DB might not be ready immediately.
    """
    import asyncio
    from urllib.parse import urlparse
    
    # Log connection details (masked)
    db_url = settings.database_url
    parsed = urlparse(db_url)
    print(f"Attempting to connect to database at {parsed.hostname}:{parsed.port or 5432}")
    
    engine = get_engine()
    max_retries = 10  # Increased retries for Railway
    retry_delay = 3  # Increased delay
    
    for attempt in range(max_retries):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            print("Database connection successful and tables initialized")
            return  # Success
        except Exception as e:
            error_msg = str(e)
            if attempt < max_retries - 1:
                print(f"Database connection attempt {attempt + 1}/{max_retries} failed: {error_msg[:100]}. Retrying in {retry_delay}s...")
                await asyncio.sleep(retry_delay)
            else:
                print(f"CRITICAL: Failed to connect to database after {max_retries} attempts")
                print(f"Error: {error_msg}")
                print(f"Database URL format: {db_url.split('@')[0] if '@' in db_url else 'N/A'}@...")
                print("Please verify:")
                print("  1. DATABASE_URL environment variable is set in Railway")
                print("  2. PostgreSQL service is running and accessible")
                print("  3. Services are properly linked in Railway")
                raise
