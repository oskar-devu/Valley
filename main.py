from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.db import init_db

# Ensure all models are registered with Base.metadata before create_all
from app import models  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
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
