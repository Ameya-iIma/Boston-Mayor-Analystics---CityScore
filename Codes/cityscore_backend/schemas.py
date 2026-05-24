from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


PeriodType = Literal["day", "week", "month", "quarter"]
Severity = Literal["green", "amber", "red", "blue"]


class DatasetStatus(BaseModel):
    dataset_name: str
    source_file: str
    row_count: int
    column_count: int
    latest_timestamp: str | None = None


class PipelineStatusResponse(BaseModel):
    refreshed_at: datetime
    current_as_of_date: date | None = None
    datasets: list[DatasetStatus]
    artifact_counts: dict[str, int]


class TopCard(BaseModel):
    period_type: PeriodType
    score: float | None = None
    previous_score: float | None = None
    change: float | None = None
    status: Severity


class AlertItem(BaseModel):
    metric_name: str
    display_name: str
    service_area: str
    owner_department: str
    selected_period: PeriodType | None = None
    current_score: float | None = None
    previous_score: float | None = None
    change_vs_previous: float | None = None
    rolling_mean_14: float | None = None
    rolling_mean_28: float | None = None
    below_target_streak: int = 0
    target: float | None = None
    actual_primary_value: float | None = None
    actual_secondary_value: float | None = None
    severity: Severity
    alert_reasons: list[str] = Field(default_factory=list)
    as_of_date: date | None = None


class ServiceAreaSummary(BaseModel):
    service_area: str
    metric_count: int
    selected_score_average: float | None = None
    day_score_average: float | None = None
    week_score_average: float | None = None
    month_score_average: float | None = None
    quarter_score_average: float | None = None
    red_count: int = 0
    amber_count: int = 0
    blue_count: int = 0
    green_count: int = 0


class ServiceAreaCoverage(BaseModel):
    service_area: str
    total_metrics: int
    metrics_with_selected_score: int
    metrics_missing_day_score: int
    actionable_alerts: int


class FreshnessResponse(BaseModel):
    as_of_date: date | None = None
    metrics_total: int
    metrics_with_day_score: int
    metrics_missing_day_score: int
    metrics_with_selected_score: int
    metrics_missing_selected_score: int
    stale_metrics: int
    actionable_alerts: int
    datasets: list[DatasetStatus]
    coverage_by_service_area: list[ServiceAreaCoverage]


class MayorDailyBriefResponse(BaseModel):
    as_of_date: date | None = None
    note: str
    top_cards: list[TopCard]
    critical_alerts: list[AlertItem]
    service_area_scorecards: list[ServiceAreaSummary]
    change_summary: dict[str, int]
    data_freshness: FreshnessResponse


class ExecutiveKpiCard(BaseModel):
    label: str
    value: str
    detail: str


class DataScopeSummary(BaseModel):
    source_focus: str
    download_date: date | None = None
    analysis_start_date: date | None = None
    analysis_end_date: date | None = None
    services_in_scope: int
    services_ranked: int
    snapshot_dates: int
    reading_note: str


class RankedServiceItem(BaseModel):
    metric_name: str
    display_name: str
    service_area: str
    owner_department: str
    classification: str
    selected_period: PeriodType | None = None
    current_score: float | None = None
    previous_score: float | None = None
    recent_trend: float | None = None
    period_average_score: float | None = None
    period_above_target_ratio: float | None = None
    ranking_score: float | None = None
    target: float | None = None
    evidence: str


class MethodologyItem(BaseModel):
    title: str
    description: str


class RecommendationItem(BaseModel):
    priority: str
    action_title: str
    owner: str
    service_area: str
    evidence: str
    recommendation: str
    next_step: str


class ExecutiveBriefResponse(BaseModel):
    headline_status: str
    headline_text: str
    supporting_text: str
    kpi_cards: list[ExecutiveKpiCard]
    data_scope: DataScopeSummary
    score_guide: list[str]
    portfolio_mix: dict[str, int]
    best_services: list[RankedServiceItem]
    worst_services: list[RankedServiceItem]
    methodology: list[MethodologyItem]
    recommendations: list[RecommendationItem]


class MetricSummary(BaseModel):
    metric_name: str
    display_name: str
    service_area: str
    owner_department: str
    cadence: str
    definition: str
    metric_logic: str | None = None
    target: float | None = None
    selected_period: PeriodType | None = None
    current_score: float | None = None
    previous_score: float | None = None
    change_vs_previous: float | None = None
    rolling_mean_14: float | None = None
    rolling_mean_28: float | None = None
    consulting_bucket: str | None = None
    performance_index: float | None = None
    priority_index: float | None = None
    severity: Severity
    alert_reasons: list[str] = Field(default_factory=list)
    as_of_date: date | None = None


class PeriodSnapshot(BaseModel):
    period_type: PeriodType
    score: float | None = None
    primary_value: float | None = None
    secondary_value: float | None = None
    previous_score: float | None = None


class MetricDetailResponse(BaseModel):
    metric_name: str
    display_name: str
    service_area: str
    owner_department: str
    cadence: str
    definition: str
    metric_logic: str | None = None
    target: float | None = None
    latest_snapshot_date: date | None = None
    selected_period: PeriodType | None = None
    current_score: float | None = None
    previous_score: float | None = None
    change_vs_previous: float | None = None
    rolling_mean_14: float | None = None
    rolling_mean_28: float | None = None
    consulting_bucket: str | None = None
    performance_index: float | None = None
    priority_index: float | None = None
    recent_trend: float | None = None
    period_average_score: float | None = None
    period_above_target_ratio: float | None = None
    recent_observation_count: int | None = None
    severity: Severity
    alert_reasons: list[str] = Field(default_factory=list)
    period_snapshots: list[PeriodSnapshot]


class MetricHistoryPoint(BaseModel):
    metric_name: str
    display_name: str
    period_type: PeriodType
    as_of_date: date
    score: float | None = None
    previous_score: float | None = None
    change_vs_previous: float | None = None
    rolling_mean_14: float | None = None
    rolling_mean_28: float | None = None
    below_target_streak: int = 0
    actual_primary_value: float | None = None
    actual_secondary_value: float | None = None
    target: float | None = None
    source: str


class CityHistoryPoint(BaseModel):
    period_type: PeriodType
    as_of_date: date
    score: float | None = None
    previous_score: float | None = None
    change: float | None = None
    metric_count: int | None = None
    source: str
