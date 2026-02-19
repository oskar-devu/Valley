from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.config import settings
from app.db.base import Base

_engine = None
_session_factory = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.database_url,
            echo=False,
            pool_pre_ping=True,  # Verify connections before using them
            pool_recycle=300,  # Recycle connections after 5 minutes
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
    
    engine = get_engine()
    max_retries = 5
    retry_delay = 2  # seconds
    
    for attempt in range(max_retries):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            return  # Success
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"Database connection attempt {attempt + 1} failed: {e}. Retrying in {retry_delay}s...")
                await asyncio.sleep(retry_delay)
            else:
                print(f"Failed to connect to database after {max_retries} attempts: {e}")
                raise
