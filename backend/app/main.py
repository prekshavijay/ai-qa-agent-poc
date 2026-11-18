"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.api.routes.requirements import router as requirements_router
from app.api.routes.test_cases import router as test_cases_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import get_logger, setup_logging
from app.database.session import init_db


setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("Starting %s (%s)", settings.app_name, settings.app_env)
    init_db()
    yield
    logger.info("Shutting down %s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    debug=settings.debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

# Top-level health for quick local checks: GET /health
app.include_router(api_router)

# Versioned API namespace for future endpoints: /api/v1/...
app.include_router(api_router, prefix=settings.api_prefix)

# Mounted once. The shared api_router is included at both / and /api/v1,
# so these routers are attached directly to keep /api/... paths stable.
app.include_router(requirements_router, prefix="/api/requirements")
app.include_router(test_cases_router, prefix="/api/test-cases")



@app.get("/", include_in_schema=False)
async def root() -> dict:
    return {
        "service": settings.app_name,
        "docs": "/docs",
        "health": "/health",
    }
