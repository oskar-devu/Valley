from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.db import init_db

# Ensure all models are registered with Base.metadata before create_all
from app import models  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Try to initialize DB, but don't fail startup if it's not ready yet
    # This allows the app to start and health checks to work
    try:
        await init_db()
    except Exception as e:
        print(f"WARNING: Database initialization failed during startup: {e}")
        print("App will start but database operations may fail until connection is established.")
        # Don't raise - allow app to start for debugging
    
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
