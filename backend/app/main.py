"""SmartShopper FastAPI application entry point."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db.client import close_mongo_connection, connect_to_mongo
from app.api.auth import router as auth_router
from app.api.v1.health import router as v1_health_router
from app.api.v1.search import router as v1_search_router
from app.api.v1.favorites import router as v1_favorites_router
from app.api.v1.rss import router as v1_rss_router
from app.rss.ingestion_worker import start_worker, stop_worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print(f"SmartShopper API starting up - Environment: {settings.ENVIRONMENT}")
    await connect_to_mongo()
    await start_worker()
    yield
    # Shutdown
    print("SmartShopper API shutting down")
    await stop_worker()
    await close_mongo_connection()


app = FastAPI(
    title="SmartShopper API",
    description="Product search and comparison with deal alerts",
    version="0.1.0",
    lifespan=lifespan
)

STATIC_DIR = Path(__file__).parent / "static"


class SPAStaticFiles(StaticFiles):
    """Static files handler with SPA fallback to index.html."""

    async def get_response(self, path: str, scope):  # type: ignore[override]
        response = await super().get_response(path, scope)
        if response.status_code == 404:
            response = await super().get_response("index.html", scope)
        return response

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(v1_health_router)
app.include_router(v1_search_router)
app.include_router(v1_favorites_router)
app.include_router(v1_rss_router)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "smartshopper-api"}


if STATIC_DIR.exists():
    app.mount("/", SPAStaticFiles(directory=STATIC_DIR, html=True), name="frontend")
else:

    @app.get("/")
    async def root():
        return {"message": "SmartShopper API", "version": "0.1.0"}
