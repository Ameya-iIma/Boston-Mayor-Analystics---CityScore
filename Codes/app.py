from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from cityscore_backend.api import router as cityscore_router
from cityscore_backend.pipeline import CityScoreRepository
from cityscore_backend.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    repository = CityScoreRepository(settings)
    frontend_dir = settings.project_root / "frontend"

    app = FastAPI(
        title="CityScore Mayor Dashboard API",
        description=(
            "Backend API for CityScore ingestion, cleaning, aggregation, alerts, "
            "and mayor-facing dashboard summaries."
        ),
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.repository = repository
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

    @app.on_event("startup")
    def warm_pipeline_cache() -> None:
        try:
            repository.refresh(persist_outputs=settings.persist_outputs_default)
        except Exception as exc:  # pragma: no cover - runtime protection
            repository.last_refresh_error = str(exc)

    @app.get("/health")
    def healthcheck() -> dict[str, str]:
        if repository.bundle is not None:
            return {"status": "ok", "message": "CityScore backend is ready."}
        if repository.last_refresh_error:
            return {"status": "degraded", "message": repository.last_refresh_error}
        return {"status": "starting", "message": "Pipeline has not been loaded yet."}

    @app.get("/")
    def root() -> dict[str, object]:
        return {
            "name": "CityScore Mayor Dashboard API",
            "docs": "/docs",
            "health": "/health",
            "pipeline_status": "/api/v1/pipeline/status",
            "dashboard_overview": "/api/v1/dashboard/overview",
            "dashboard_ui": "/dashboard",
        }

    @app.get("/dashboard", include_in_schema=False)
    def dashboard() -> FileResponse:
        return FileResponse(frontend_dir / "index.html")

    app.include_router(cityscore_router)
    return app


app = create_app()
