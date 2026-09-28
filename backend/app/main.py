import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import models  # noqa: F401  (register tables)
from .config import settings
from .database import Base, SessionLocal, engine, ensure_schema_compatibility
from .routers import auth, batches, dashboard, demo, farmers, inspections, standards
from .seed import seed
from .services.vision import backend_name

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    ensure_schema_compatibility()
    with SessionLocal() as db:
        seed(db)
    logging.getLogger("startup").info("Vision backend: %s", backend_name())
    yield


app = FastAPI(title="Kanda QA - AI onion quality inspection", version="1.0.0", lifespan=lifespan)

for r in (auth, farmers, batches, inspections, standards, dashboard, demo):
    app.include_router(r.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "vision_backend": backend_name()}


@app.exception_handler(ValueError)
async def value_error_handler(_, exc: ValueError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


if settings.frontend_dir.exists():
    app.mount("/", StaticFiles(directory=settings.frontend_dir, html=True), name="frontend")
