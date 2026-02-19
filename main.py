from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.db import init_db

# Ensure all models are registered with Base.metadata before create_all
from app import models  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Log startup info
    import os
    print("=" * 60)
    print("Application starting up...")
    print(f"Environment: {'Railway' if os.getenv('RAILWAY_ENVIRONMENT') else 'Local'}")
    
    # Check if DATABASE_URL is set
    db_url_env = os.getenv("DATABASE_URL")
    if db_url_env:
        print(f"✓ DATABASE_URL found in environment")
    else:
        print("⚠ DATABASE_URL NOT found in environment variables!")
        print("  Please ensure PostgreSQL service is added and linked in Railway")
    
    # Try to initialize DB
    try:
        await init_db()
        print("✓ Database initialized successfully")
    except Exception as e:
        print(f"✗ Database initialization failed: {e}")
        print("\nTROUBLESHOOTING:")
        print("1. In Railway dashboard, check if PostgreSQL service exists")
        print("2. Ensure PostgreSQL service is linked to your app service")
        print("3. Check Variables tab - DATABASE_URL should be auto-set by Railway")
        print("4. Verify PostgreSQL service is running (not paused)")
        raise  # Fail startup so Railway shows the error
    
    print("=" * 60)
    
    yield
    # shutdown: close engine if needed
    from app.db.session import get_engine
    engine = get_engine()
    await engine.dispose()


app = FastAPI(
    title="Valley – LinkedIn Sequence API",
    description="Generate personalized LinkedIn messaging sequences from prospect URLs and company context.",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok"}
