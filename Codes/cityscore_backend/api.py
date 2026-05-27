from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from .pipeline import CityScoreRepository
from .schemas import (
    AlertItem,
    CityHistoryPoint,
    ExecutiveBriefResponse,
    FreshnessResponse,
    MayorDailyBriefResponse,
    MetricDetailResponse,
    MetricHistoryPoint,
    MetricSummary,
    PipelineStatusResponse,
    ServiceAreaSummary,
)


router = APIRouter(prefix="/api/v1", tags=["cityscore"])


def get_repository(request: Request) -> CityScoreRepository:
    return request.app.state.repository


def get_ready_repository(repository: CityScoreRepository = Depends(get_repository)) -> CityScoreRepository:
    try:
        repository.ensure_ready()
        return repository
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - runtime protection
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/pipeline/status", response_model=PipelineStatusResponse)
def get_pipeline_status(repository: CityScoreRepository = Depends(get_ready_repository)) -> dict:
    return repository.get_pipeline_status()


@router.post("/pipeline/refresh", response_model=PipelineStatusResponse)
def refresh_pipeline(
    persist_outputs: bool = Query(default=True),
    repository: CityScoreRepository = Depends(get_repository),
) -> dict:
    try:
        return repository.refresh(persist_outputs=persist_outputs)
    except Exception as exc:  # pragma: no cover - runtime protection
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/dashboard/overview", response_model=MayorDailyBriefResponse)
def get_dashboard_overview(repository: CityScoreRepository = Depends(get_ready_repository)) -> dict:
    return repository.get_daily_brief()


@router.get("/dashboard/executive-brief", response_model=ExecutiveBriefResponse)
def get_dashboard_executive_brief(repository: CityScoreRepository = Depends(get_ready_repository)) -> dict:
    return repository.get_executive_brief()


@router.get("/dashboard/city-history", response_model=list[CityHistoryPoint])
def get_city_history(
    days: int = Query(default=180, ge=30, le=3650),
    repository: CityScoreRepository = Depends(get_ready_repository),
) -> list[dict]:
    return repository.get_city_history(days=days)


@router.get("/dashboard/alerts", response_model=list[AlertItem])
def get_dashboard_alerts(
    severity: str | None = Query(default=None),
    service_area: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    include_green: bool = Query(default=False),
    repository: CityScoreRepository = Depends(get_ready_repository),
) -> list[dict]:
    return repository.get_alerts(
        severity=severity,
        service_area=service_area,
        limit=limit,
        include_green=include_green,
    )


@router.get("/dashboard/service-areas", response_model=list[ServiceAreaSummary])
def get_service_area_cards(repository: CityScoreRepository = Depends(get_ready_repository)) -> list[dict]:
    return repository.get_service_area_summary()


@router.get("/dashboard/freshness", response_model=FreshnessResponse)
def get_dashboard_freshness(repository: CityScoreRepository = Depends(get_ready_repository)) -> dict:
    return repository.get_freshness()


@router.get("/metrics", response_model=list[MetricSummary])
def list_metrics(
    service_area: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    query: str | None = Query(default=None),
    repository: CityScoreRepository = Depends(get_ready_repository),
) -> list[dict]:
    return repository.list_metrics(service_area=service_area, severity=severity, query=query)


@router.get("/metrics/{metric_name}", response_model=MetricDetailResponse)
def get_metric_detail(metric_name: str, repository: CityScoreRepository = Depends(get_ready_repository)) -> dict:
    try:
        return repository.get_metric_detail(metric_name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown metric: {metric_name}") from exc


@router.get("/metrics/{metric_name}/history", response_model=list[MetricHistoryPoint])
def get_metric_history(
    metric_name: str,
    period_type: str | None = Query(default=None, pattern="^(day|week|month|quarter)$"),
    days: int = Query(default=90, ge=7, le=3650),
    repository: CityScoreRepository = Depends(get_ready_repository),
) -> list[dict]:
    try:
        return repository.get_metric_history(metric_name=metric_name, period_type=period_type, days=days)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown metric: {metric_name}") from exc
