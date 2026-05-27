from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from .metric_catalog import SERVICE_AREA_ORDER, get_metric_metadata, normalize_metric_name
from .settings import Settings


CURRENT_PERIOD_MAP = {
    "day": {"score": "day_score", "primary": "day_numerator", "secondary": "day_denominator"},
    "week": {"score": "week_score", "primary": "week_numerator", "secondary": "week_denominator"},
    "month": {"score": "month_score", "primary": "month_numerator", "secondary": "month_denominator"},
    "quarter": {"score": "quarter_score", "primary": "quarter_numerator", "secondary": "quarter_denominator"},
}

CURRENT_SUMMARY_PREVIOUS_MAP = {
    "day": "previous_day_score",
    "week": "previous_week_score",
    "month": "previous_month_score",
    "quarter": "previous_quarter_score",
}

HISTORICAL_PERIOD_MAP = {
    "day": {"score": "cty_scr_day", "primary": "cty_scr_nbr_dy_01", "secondary": "cty_scr_nbr_dy_02"},
    "week": {"score": "cty_scr_week", "primary": "cty_scr_nbr_wk_01", "secondary": "cty_scr_nbr_wk_02"},
    "month": {"score": "cty_scr_month", "primary": "cty_scr_nbr_mo_01", "secondary": "cty_scr_nbr_mo_02"},
    "quarter": {"score": "cty_scr_quarter", "primary": "cty_scr_nbr_qt_01", "secondary": "cty_scr_nbr_qt_02"},
}

CITY_AGG_PERIOD_MAP = {
    "day": "cty_scr_day_agg",
    "week": "cty_scr_week_agg",
    "month": "cty_scr_month_agg",
    "quarter": "cty_scr_quarter_agg",
}

HISTORY_PERIOD_POINT_LIMITS = {
    "day": 90,
    "week": 52,
    "month": 24,
    "quarter": 16,
}

HISTORY_PERIOD_FREQUENCIES = {
    "week": "W",
    "month": "M",
    "quarter": "Q",
}

SEVERITY_RANK = {"red": 0, "amber": 1, "blue": 2, "green": 3}
NOTEBOOK_TOP_EXCLUSIONS = {"HOMICIDES (TREND)", "SHOOTINGS (TREND)", "LIBRARY USERS"}
PERFORMANCE_BAND_THRESHOLDS = [
    ("CRITICAL", 0.70, "score < 0.70"),
    ("AT RISK", 0.90, "score 0.70–0.89"),
    ("NEAR MISS", 1.00, "score 0.90–0.99"),
    ("ON TARGET", 1.10, "score 1.00–1.09"),
    ("EXCEEDING", float("inf"), "score ≥ 1.10"),
]


@dataclass
class DataBundle:
    cleaned_frames: dict[str, pd.DataFrame]
    dataset_status: list[dict[str, Any]]
    metric_master: pd.DataFrame
    metric_history_long: pd.DataFrame
    city_score_history: pd.DataFrame
    latest_metric_snapshot: pd.DataFrame
    alerts: pd.DataFrame
    service_area_summary: pd.DataFrame
    freshness: dict[str, Any]
    mayor_daily_brief: dict[str, Any]
    executive_brief: dict[str, Any]
    refreshed_at: datetime
    current_as_of_date: date | None


class CityScoreRepository:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.bundle: DataBundle | None = None
        self.last_refresh_error: str | None = None

    def ensure_ready(self) -> None:
        if self.bundle is None:
            self.refresh(persist_outputs=self.settings.persist_outputs_default)

    def refresh(self, persist_outputs: bool | None = None) -> dict[str, Any]:
        if persist_outputs is None:
            persist_outputs = self.settings.persist_outputs_default
        self.settings.ensure_directories()
        self.settings.validate_input_files()

        try:
            raw_frames = self._load_raw_frames()
            cleaned_frames = self._clean_raw_frames(raw_frames)
            dataset_status = self._build_dataset_status(cleaned_frames)
            metric_master = self._build_metric_master(cleaned_frames)
            metric_history_long = self._build_metric_history_long(cleaned_frames)
            city_score_history = self._build_city_score_history(cleaned_frames, metric_history_long)
            latest_metric_snapshot = self._build_latest_metric_snapshot(
                cleaned_frames=cleaned_frames,
                metric_master=metric_master,
                metric_history_long=metric_history_long,
            )
            alerts = self._build_alerts(latest_metric_snapshot)
            service_area_summary = self._build_service_area_summary(latest_metric_snapshot)
            freshness = self._build_freshness_payload(
                dataset_status=dataset_status,
                latest_metric_snapshot=latest_metric_snapshot,
            )
            executive_brief = self._build_executive_brief_payload(
                cleaned_frames=cleaned_frames,
                latest_metric_snapshot=latest_metric_snapshot,
                service_area_summary=service_area_summary,
                freshness=freshness,
            )
            mayor_daily_brief = self._build_mayor_daily_brief_payload(
                city_score_history=city_score_history,
                latest_metric_snapshot=latest_metric_snapshot,
                alerts=alerts,
                service_area_summary=service_area_summary,
                freshness=freshness,
            )

            refreshed_at = datetime.utcnow()
            current_as_of_date = self._safe_date_value(
                latest_metric_snapshot["as_of_date"].max() if not latest_metric_snapshot.empty else None
            )

            if persist_outputs:
                self._write_cleaned_outputs(cleaned_frames)
                self._write_aggregated_outputs(
                    metric_master=metric_master,
                    metric_history_long=metric_history_long,
                    city_score_history=city_score_history,
                    latest_metric_snapshot=latest_metric_snapshot,
                    alerts=alerts,
                    service_area_summary=service_area_summary,
                    executive_brief=executive_brief,
                )

            self.bundle = DataBundle(
                cleaned_frames=cleaned_frames,
                dataset_status=dataset_status,
                metric_master=metric_master,
                metric_history_long=metric_history_long,
                city_score_history=city_score_history,
                latest_metric_snapshot=latest_metric_snapshot,
                alerts=alerts,
                service_area_summary=service_area_summary,
                freshness=freshness,
                mayor_daily_brief=mayor_daily_brief,
                executive_brief=executive_brief,
                refreshed_at=refreshed_at,
                current_as_of_date=current_as_of_date,
            )
            self.last_refresh_error = None
            return self.get_pipeline_status()
        except Exception as exc:  # pragma: no cover - defensive branch for runtime issues
            self.last_refresh_error = str(exc)
            raise

    def get_pipeline_status(self) -> dict[str, Any]:
        self.ensure_ready()
        assert self.bundle is not None
        return {
            "refreshed_at": self.bundle.refreshed_at,
            "current_as_of_date": self.bundle.current_as_of_date,
            "datasets": self.bundle.dataset_status,
            "artifact_counts": {
                "metric_master": int(len(self.bundle.metric_master)),
                "metric_history_long": int(len(self.bundle.metric_history_long)),
                "city_score_history": int(len(self.bundle.city_score_history)),
                "latest_metric_snapshot": int(len(self.bundle.latest_metric_snapshot)),
                "alerts": int(len(self.bundle.alerts)),
                "service_area_summary": int(len(self.bundle.service_area_summary)),
            },
        }

    def get_daily_brief(self) -> dict[str, Any]:
        self.ensure_ready()
        assert self.bundle is not None
        return self.bundle.mayor_daily_brief

    def get_executive_brief(self) -> dict[str, Any]:
        self.ensure_ready()
        assert self.bundle is not None
        return self.bundle.executive_brief

    def get_freshness(self) -> dict[str, Any]:
        self.ensure_ready()
        assert self.bundle is not None
        return self.bundle.freshness

    def get_city_history(self, days: int = 180) -> list[dict[str, Any]]:
        self.ensure_ready()
        assert self.bundle is not None

        history = self.bundle.city_score_history.copy()
        latest_as_of_date = history["as_of_date"].max()
        if pd.notna(latest_as_of_date):
            cutoff_date = latest_as_of_date - pd.Timedelta(days=days)
            history = history[history["as_of_date"] >= cutoff_date]

        history = history.sort_values(["period_type", "as_of_date"])
        return [
            {
                "period_type": row["period_type"],
                "as_of_date": self._safe_date_value(row["as_of_date"]),
                "score": self._safe_float_value(row.get("score")),
                "previous_score": self._safe_float_value(row.get("previous_score")),
                "change": self._safe_float_value(row.get("change")),
                "metric_count": None if pd.isna(row.get("metric_count")) else int(row.get("metric_count")),
                "source": row["source"],
            }
            for _, row in history.iterrows()
        ]

    def get_service_area_summary(self) -> list[dict[str, Any]]:
        self.ensure_ready()
        assert self.bundle is not None
        return [self._service_area_record(row) for _, row in self.bundle.service_area_summary.iterrows()]

    def get_alerts(
        self,
        severity: str | None = None,
        service_area: str | None = None,
        limit: int = 50,
        include_green: bool = False,
    ) -> list[dict[str, Any]]:
        self.ensure_ready()
        assert self.bundle is not None

        alerts = self.bundle.latest_metric_snapshot.copy()
        if not include_green:
            alerts = alerts[alerts["severity"] != "green"]
        if severity:
            alerts = alerts[alerts["severity"].str.lower() == severity.lower()]
        if service_area:
            alerts = alerts[alerts["service_area"].str.lower() == service_area.lower()]

        alerts = alerts.sort_values(
            ["severity_rank", "selected_score_sort", "display_name"],
            ascending=[True, True, True],
        ).head(limit)
        return [self._alert_record(row) for _, row in alerts.iterrows()]

    def list_metrics(
        self,
        service_area: str | None = None,
        severity: str | None = None,
        query: str | None = None,
    ) -> list[dict[str, Any]]:
        self.ensure_ready()
        assert self.bundle is not None

        metrics = self.bundle.latest_metric_snapshot.copy()
        if service_area:
            metrics = metrics[metrics["service_area"].str.lower() == service_area.lower()]
        if severity:
            metrics = metrics[metrics["severity"].str.lower() == severity.lower()]
        if query:
            query_value = query.strip().lower()
            metrics = metrics[
                metrics["metric_name"].str.lower().str.contains(query_value)
                | metrics["display_name"].str.lower().str.contains(query_value)
            ]

        metrics = metrics.sort_values(["service_area_order", "display_name"])
        return [self._metric_summary_record(row) for _, row in metrics.iterrows()]

    def get_metric_detail(self, metric_name: str) -> dict[str, Any]:
        self.ensure_ready()
        assert self.bundle is not None

        canonical_name = normalize_metric_name(metric_name)
        matching = self.bundle.latest_metric_snapshot[self.bundle.latest_metric_snapshot["metric_name"] == canonical_name]
        if matching.empty:
            raise KeyError(canonical_name)

        row = matching.iloc[0]
        period_snapshots = []
        for period in CURRENT_PERIOD_MAP:
            period_snapshots.append(
                {
                    "period_type": period,
                    "score": self._safe_float_value(row.get(f"{period}_score")),
                    "primary_value": self._safe_float_value(row.get(f"{period}_numerator")),
                    "secondary_value": self._safe_float_value(row.get(f"{period}_denominator")),
                    "previous_score": self._safe_float_value(row.get(f"{period}_previous_score")),
                }
            )

        return {
            "metric_name": row["metric_name"],
            "display_name": row["display_name"],
            "service_area": row["service_area"],
            "owner_department": row["owner_department"],
            "department": self._safe_text_value(row.get("department")),
            "cadence": row["cadence"],
            "definition": row["definition"],
            "metric_logic": self._safe_text_value(row.get("metric_logic")),
            "target": self._safe_float_value(row.get("target")),
            "latest_snapshot_date": self._safe_date_value(row.get("as_of_date")),
            "selected_period": self._safe_period_value(row.get("selected_period")),
            "current_score": self._safe_float_value(row.get("selected_score")),
            "previous_score": self._safe_float_value(row.get("previous_score")),
            "change_vs_previous": self._safe_float_value(row.get("change_vs_previous")),
            "rolling_mean_14": self._safe_float_value(row.get("rolling_mean_14")),
            "rolling_mean_28": self._safe_float_value(row.get("rolling_mean_28")),
            "consulting_bucket": self._safe_text_value(row.get("consulting_bucket")),
            "performance_index": self._safe_float_value(row.get("performance_index")),
            "priority_index": self._safe_float_value(row.get("priority_index")),
            "recent_trend": self._safe_float_value(row.get("recent_trend")),
            "period_average_score": self._safe_float_value(row.get("period_average_score")),
            "period_above_target_ratio": self._safe_float_value(row.get("period_above_target_ratio")),
            "recent_observation_count": self._safe_int_value(row.get("recent_observation_count")),
            "composite_score": self._safe_float_value(row.get("composite_score")),
            "gap_to_target": self._safe_float_value(row.get("gap_to_target")),
            "day_score_final": self._safe_float_value(row.get("day_score_final")),
            "trend_delta_dw": self._safe_float_value(row.get("trend_delta_dw")),
            "trend_delta_wq": self._safe_float_value(row.get("trend_delta_wq")),
            "trend_delta_mq": self._safe_float_value(row.get("trend_delta_mq")),
            "trend_label": self._safe_text_value(row.get("trend_label")),
            "perf_band": self._safe_text_value(row.get("perf_band")),
            "severity": row["severity"],
            "alert_reasons": row["alert_reasons"],
            "period_snapshots": period_snapshots,
        }

    def get_metric_history(
        self,
        metric_name: str,
        period_type: str | None = None,
        days: int = 90,
    ) -> list[dict[str, Any]]:
        self.ensure_ready()
        assert self.bundle is not None

        canonical_name = normalize_metric_name(metric_name)
        history = self.bundle.metric_history_long[self.bundle.metric_history_long["metric_name"] == canonical_name].copy()
        if history.empty:
            raise KeyError(canonical_name)

        normalized_period = period_type.lower() if isinstance(period_type, str) else None
        if normalized_period:
            history = history[history["period_type"] == normalized_period]

        history = history[history["score"].notna()].copy()
        if history.empty:
            return []

        if normalized_period:
            history = self._aggregate_metric_history_for_period(history, normalized_period)
            history = history.sort_values("as_of_date").tail(
                HISTORY_PERIOD_POINT_LIMITS.get(normalized_period, 90)
            )
        else:
            latest_as_of_date = history["as_of_date"].max()
            if pd.notna(latest_as_of_date):
                cutoff_date = latest_as_of_date - pd.Timedelta(days=days)
                history = history[history["as_of_date"] >= cutoff_date]

        history = history.sort_values(["period_type", "as_of_date"]).copy()
        grouped = history.groupby(["metric_name", "period_type"], group_keys=False)
        history["previous_score"] = grouped["score"].shift(1)
        history["change_vs_previous"] = history["score"] - history["previous_score"]

        return [self._history_record(row) for _, row in history.iterrows()]

    def _aggregate_metric_history_for_period(self, history: pd.DataFrame, period_type: str) -> pd.DataFrame:
        if period_type == "day":
            return history.sort_values("as_of_date").copy()

        frequency = HISTORY_PERIOD_FREQUENCIES.get(period_type)
        if not frequency:
            return history.sort_values("as_of_date").copy()

        aggregated = history.copy()
        aggregated["as_of_date"] = pd.to_datetime(aggregated["as_of_date"], errors="coerce")
        aggregated = aggregated[aggregated["as_of_date"].notna()].copy()
        if aggregated.empty:
            return aggregated
        aggregated["period_bucket"] = aggregated["as_of_date"].dt.to_period(frequency)
        aggregated = (
            aggregated.sort_values(["period_bucket", "as_of_date"])
            .groupby("period_bucket", as_index=False)
            .tail(1)
            .drop(columns=["period_bucket"])
        )
        return aggregated.sort_values("as_of_date").copy()

    def _load_raw_frames(self) -> dict[str, pd.DataFrame]:
        return {
            dataset_name: pd.read_excel(path)
            for dataset_name, path in self.settings.raw_files.items()
        }

    def _clean_raw_frames(self, raw_frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
        return {
            "current_full_metrics": self._clean_current_full_metrics(raw_frames["current_full_metrics"]),
            "current_summary": self._clean_current_summary(raw_frames["current_summary"]),
            "historical_city_agg": self._clean_historical_city_agg(raw_frames["historical_city_agg"]),
            "historical_metric_summary": self._clean_historical_metric_summary(raw_frames["historical_metric_summary"]),
        }

    def _clean_current_full_metrics(self, df: pd.DataFrame) -> pd.DataFrame:
        cleaned = self._base_clean(df)
        cleaned = self._convert_excel_serial_dates(cleaned, ["score_calculated_ts"])
        cleaned["metric_name"] = cleaned["metric_name"].map(normalize_metric_name)
        cleaned = self._coerce_numeric_columns(
            cleaned,
            skip_columns={"metric_name", "metric_logic", "score_calculated_ts", "latest_score_flag"},
        )
        cleaned["latest_score_flag"] = pd.to_numeric(cleaned["latest_score_flag"], errors="coerce").fillna(0).astype(int)
        return cleaned.sort_values(["metric_name", "score_calculated_ts"]).reset_index(drop=True)

    def _clean_current_summary(self, df: pd.DataFrame) -> pd.DataFrame:
        cleaned = self._base_clean(df)
        cleaned = self._convert_excel_serial_dates(cleaned, ["score_calculated_ts", "score_final_table_ts"])
        cleaned["metric_name"] = cleaned["metric_name"].map(normalize_metric_name)
        cleaned = self._coerce_numeric_columns(
            cleaned,
            skip_columns={"metric_name", "score_calculated_ts", "score_final_table_ts", "score_day_name"},
        )
        return cleaned.sort_values(["metric_name", "score_final_table_ts"]).reset_index(drop=True)

    def _clean_historical_city_agg(self, df: pd.DataFrame) -> pd.DataFrame:
        cleaned = self._base_clean(df)
        cleaned = self._convert_excel_serial_dates(cleaned, ["etl_load_date"])
        cleaned = self._coerce_numeric_columns(
            cleaned,
            skip_columns={"etl_load_date", "etl_load_is_active_flag"},
        )
        return cleaned.sort_values("etl_load_date").reset_index(drop=True)

    def _clean_historical_metric_summary(self, df: pd.DataFrame) -> pd.DataFrame:
        cleaned = self._base_clean(df)
        cleaned = self._convert_excel_serial_dates(cleaned, ["etl_load_date"])
        cleaned["cty_scr_name"] = cleaned["cty_scr_name"].map(normalize_metric_name)
        cleaned = self._coerce_numeric_columns(
            cleaned,
            skip_columns={
                "cty_scr_name",
                "etl_load_date",
                "etl_load_is_active_flag",
                "cty_scr_open_data_source",
                "cty_scr_metric_type",
                "cty_scr_day_name",
            },
        )
        return cleaned.sort_values(["cty_scr_name", "etl_load_date"]).reset_index(drop=True)

    def _base_clean(self, df: pd.DataFrame) -> pd.DataFrame:
        cleaned = self._snake_case_columns(df)
        cleaned = self._strip_text_values(cleaned)
        cleaned = self._drop_empty_rows_and_columns(cleaned)
        return cleaned

    def _build_dataset_status(self, cleaned_frames: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
        timestamp_columns = {
            "current_full_metrics": "score_calculated_ts",
            "current_summary": "score_final_table_ts",
            "historical_city_agg": "etl_load_date",
            "historical_metric_summary": "etl_load_date",
        }

        status_rows = []
        for dataset_name, frame in cleaned_frames.items():
            latest_timestamp = None
            timestamp_column = timestamp_columns.get(dataset_name)
            if timestamp_column and timestamp_column in frame.columns and not frame.empty:
                latest_timestamp = self._safe_datetime_string(frame[timestamp_column].max())

            status_rows.append(
                {
                    "dataset_name": dataset_name,
                    "source_file": self.settings.raw_files[dataset_name].name,
                    "row_count": int(frame.shape[0]),
                    "column_count": int(frame.shape[1]),
                    "latest_timestamp": latest_timestamp,
                }
            )

        return status_rows

    def _build_metric_master(self, cleaned_frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
        metrics = set(cleaned_frames["current_full_metrics"]["metric_name"].dropna().tolist())
        metrics.update(cleaned_frames["current_summary"]["metric_name"].dropna().tolist())
        metrics.update(cleaned_frames["historical_metric_summary"]["cty_scr_name"].dropna().tolist())

        latest_detail = (
            cleaned_frames["current_full_metrics"]
            .sort_values(["metric_name", "latest_score_flag", "score_calculated_ts"])
            .groupby("metric_name", as_index=False)
            .tail(1)
            .set_index("metric_name")
        )

        rows = []
        historical_metric_names = set(cleaned_frames["historical_metric_summary"]["cty_scr_name"].dropna().tolist())
        current_summary_metric_names = set(cleaned_frames["current_summary"]["metric_name"].dropna().tolist())
        current_detail_metric_names = set(cleaned_frames["current_full_metrics"]["metric_name"].dropna().tolist())

        for metric_name in sorted(metrics):
            metadata = get_metric_metadata(metric_name)
            latest_row = latest_detail.loc[metric_name] if metric_name in latest_detail.index else None

            rows.append(
                {
                    "metric_name": metric_name,
                    "display_name": metadata["display_name"],
                    "service_area": metadata["service_area"],
                    "owner_department": metadata["owner_department"],
                    "cadence": metadata["cadence"],
                    "definition": metadata["definition"],
                    "default_metric_logic": latest_row.get("metric_logic") if latest_row is not None else None,
                    "default_target": self._safe_float_value(latest_row.get("target")) if latest_row is not None else None,
                    "has_current_detail": metric_name in current_detail_metric_names,
                    "has_current_summary": metric_name in current_summary_metric_names,
                    "has_history": metric_name in historical_metric_names,
                }
            )

        master = pd.DataFrame(rows)
        master["service_area_order"] = master["service_area"].map(self._service_area_order)
        return master.sort_values(["service_area_order", "display_name"]).reset_index(drop=True)

    def _build_metric_history_long(self, cleaned_frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
        current_detail = cleaned_frames["current_full_metrics"]
        historical_metric_summary = cleaned_frames["historical_metric_summary"]

        current_records = []
        for period_type, column_map in CURRENT_PERIOD_MAP.items():
            subset = current_detail[
                [
                    "metric_name",
                    "score_calculated_ts",
                    "target",
                    "metric_logic",
                    column_map["score"],
                    column_map["primary"],
                    column_map["secondary"],
                ]
            ].copy()
            subset["period_type"] = period_type
            subset["score"] = subset[column_map["score"]]
            subset["actual_primary_value"] = subset[column_map["primary"]]
            subset["actual_secondary_value"] = subset[column_map["secondary"]]
            subset["source"] = "current_full_snapshot"
            subset["as_of_date"] = subset["score_calculated_ts"].dt.normalize()
            current_records.append(
                subset[
                    [
                        "metric_name",
                        "period_type",
                        "as_of_date",
                        "score_calculated_ts",
                        "score",
                        "actual_primary_value",
                        "actual_secondary_value",
                        "target",
                        "metric_logic",
                        "source",
                    ]
                ]
            )

        historical_records = []
        for period_type, column_map in HISTORICAL_PERIOD_MAP.items():
            subset = historical_metric_summary[
                [
                    "cty_scr_name",
                    "etl_load_date",
                    "cty_scr_tgt_01",
                    column_map["score"],
                    column_map["primary"],
                    column_map["secondary"],
                ]
            ].copy()
            subset["period_type"] = period_type
            subset["metric_name"] = subset["cty_scr_name"]
            subset["score"] = subset[column_map["score"]]
            subset["actual_primary_value"] = subset[column_map["primary"]]
            subset["actual_secondary_value"] = subset[column_map["secondary"]]
            subset["target"] = subset["cty_scr_tgt_01"]
            subset["metric_logic"] = pd.NA
            subset["source"] = "historical_metric_report"
            subset["as_of_date"] = subset["etl_load_date"].dt.normalize()
            subset["score_calculated_ts"] = subset["etl_load_date"]
            historical_records.append(
                subset[
                    [
                        "metric_name",
                        "period_type",
                        "as_of_date",
                        "score_calculated_ts",
                        "score",
                        "actual_primary_value",
                        "actual_secondary_value",
                        "target",
                        "metric_logic",
                        "source",
                    ]
                ]
            )

        history = pd.concat(current_records + historical_records, ignore_index=True)
        history = history[
            history[["score", "actual_primary_value", "actual_secondary_value", "target"]].notna().any(axis=1)
        ].copy()

        history["source_rank"] = history["source"].map(
            {"historical_metric_report": 0, "current_full_snapshot": 1}
        )
        history = history.sort_values(
            ["metric_name", "period_type", "as_of_date", "source_rank", "score_calculated_ts"]
        ).drop_duplicates(
            subset=["metric_name", "period_type", "as_of_date"], keep="last"
        )

        metric_metadata = history["metric_name"].map(get_metric_metadata)
        history["display_name"] = metric_metadata.map(lambda item: item["display_name"])
        history["service_area"] = metric_metadata.map(lambda item: item["service_area"])
        history["owner_department"] = metric_metadata.map(lambda item: item["owner_department"])

        grouped = history.groupby(["metric_name", "period_type"], group_keys=False)
        history["previous_score"] = grouped["score"].shift(1)
        history["change_vs_previous"] = history["score"] - history["previous_score"]
        history["below_target_streak"] = grouped["score"].transform(self._compute_below_target_streak)
        history["recent_decline_flag"] = grouped["score"].transform(self._compute_recent_decline_flag).astype(bool)
        for window in self.settings.rolling_windows:
            history[f"rolling_mean_{window}"] = grouped["score"].transform(
                lambda scores, rolling_window=window: scores.shift(1).rolling(rolling_window, min_periods=3).mean()
            )

        history["service_area_order"] = history["service_area"].map(self._service_area_order)
        return history.sort_values(
            ["service_area_order", "display_name", "period_type", "as_of_date"]
        ).reset_index(drop=True)

    def _build_city_score_history(
        self,
        cleaned_frames: dict[str, pd.DataFrame],
        metric_history_long: pd.DataFrame,
    ) -> pd.DataFrame:
        historical_city_agg = cleaned_frames["historical_city_agg"]
        historical_records = []
        for period_type, score_column in CITY_AGG_PERIOD_MAP.items():
            subset = historical_city_agg[["etl_load_date", score_column]].copy()
            subset["period_type"] = period_type
            subset["as_of_date"] = subset["etl_load_date"].dt.normalize()
            subset["score"] = subset[score_column]
            subset["metric_count"] = pd.NA
            subset["source"] = "historical_city_aggregate"
            historical_records.append(
                subset[["period_type", "as_of_date", "score", "metric_count", "source"]]
            )

        current_metric_history = metric_history_long[metric_history_long["source"] == "current_full_snapshot"].copy()
        current_derived = (
            current_metric_history.groupby(["period_type", "as_of_date"], as_index=False)
            .agg(score=("score", "mean"), metric_count=("score", "count"))
        )
        current_derived["source"] = "derived_current_city_aggregate"

        city_history = pd.concat(historical_records + [current_derived], ignore_index=True)
        city_history = city_history[city_history["score"].notna()].copy()
        city_history = city_history.sort_values(["period_type", "as_of_date", "source"]).drop_duplicates(
            subset=["period_type", "as_of_date"], keep="last"
        )

        grouped = city_history.groupby("period_type", group_keys=False)
        city_history["previous_score"] = grouped["score"].shift(1)
        city_history["change"] = city_history["score"] - city_history["previous_score"]
        return city_history.sort_values(["period_type", "as_of_date"]).reset_index(drop=True)

    def _build_latest_metric_snapshot(
        self,
        cleaned_frames: dict[str, pd.DataFrame],
        metric_master: pd.DataFrame,
        metric_history_long: pd.DataFrame,
    ) -> pd.DataFrame:
        current_detail = cleaned_frames["current_full_metrics"]
        current_summary = cleaned_frames["current_summary"]

        latest_detail = (
            current_detail.sort_values(["metric_name", "latest_score_flag", "score_calculated_ts"])
            .groupby("metric_name", as_index=False)
            .tail(1)
        )
        latest_summary = (
            current_summary.sort_values(["metric_name", "score_final_table_ts", "score_calculated_ts"])
            .groupby("metric_name", as_index=False)
            .tail(1)
        )

        latest = metric_master.merge(latest_detail, on="metric_name", how="left")
        latest = latest.merge(
            latest_summary[
                [
                    "metric_name",
                    "score_final_table_ts",
                    "previous_day_score",
                    "previous_week_score",
                    "previous_month_score",
                    "previous_quarter_score",
                    "score_day_name",
                ]
            ],
            on="metric_name",
            how="left",
        )

        latest["target"] = latest["target"].combine_first(latest["default_target"])
        latest["metric_logic"] = latest["metric_logic"].combine_first(latest["default_metric_logic"])
        latest["as_of_date"] = latest["score_calculated_ts"].dt.normalize()

        latest["selected_period"] = latest.apply(self._pick_selected_period, axis=1)
        latest["selected_score"] = latest.apply(
            lambda row: self._extract_period_value(row, row.get("selected_period"), "score"),
            axis=1,
        )
        latest["actual_primary_value"] = latest.apply(
            lambda row: self._extract_period_value(row, row.get("selected_period"), "numerator"),
            axis=1,
        )
        latest["actual_secondary_value"] = latest.apply(
            lambda row: self._extract_period_value(row, row.get("selected_period"), "denominator"),
            axis=1,
        )
        latest["summary_previous_score"] = latest.apply(
            self._extract_summary_previous_score,
            axis=1,
        )
        for period_type in CURRENT_PERIOD_MAP:
            latest[f"{period_type}_previous_score"] = latest[CURRENT_SUMMARY_PREVIOUS_MAP[period_type]]
        latest["day_score_final"] = latest["previous_day_score"].combine_first(latest["day_score"])
        latest["composite_score"] = (
            latest["quarter_score"]
            .combine_first(latest["month_score"])
            .combine_first(latest["week_score"])
        )
        latest["gap_to_target"] = latest["composite_score"] - 1.0
        latest["gap_above_target"] = (latest["composite_score"] - 1.0).clip(lower=0)
        latest["trend_delta_wq"] = latest["week_score"] - latest["quarter_score"]
        latest["trend_delta_dw"] = latest["day_score_final"] - latest["week_score"]
        latest["trend_delta_mq"] = latest["month_score"] - latest["quarter_score"]
        latest["trend_label"] = latest["trend_delta_wq"].apply(self._trend_label)
        latest["perf_band"] = latest["composite_score"].apply(self._performance_band)
        latest["department"] = latest["metric_name"].apply(self._categorize_department)

        history_lookup = metric_history_long.sort_values(["metric_name", "period_type", "as_of_date"]).groupby(
            ["metric_name", "period_type"], as_index=False
        ).tail(1)
        history_lookup = history_lookup.rename(
            columns={
                "period_type": "selected_period",
                "previous_score": "history_previous_score",
                "change_vs_previous": "history_change_vs_previous",
                "below_target_streak": "history_below_target_streak",
                "recent_decline_flag": "history_recent_decline_flag",
            }
        )

        latest = latest.merge(
            history_lookup[
                [
                    "metric_name",
                    "selected_period",
                    "rolling_mean_14",
                    "rolling_mean_28",
                    "history_previous_score",
                    "history_change_vs_previous",
                    "history_below_target_streak",
                    "history_recent_decline_flag",
                ]
            ],
            on=["metric_name", "selected_period"],
            how="left",
        )

        recent_summary = self._build_recent_selected_period_summary(metric_history_long)
        latest = latest.merge(
            recent_summary,
            on=["metric_name", "selected_period"],
            how="left",
        )

        score_columns = [f"{period_type}_score" for period_type in CURRENT_PERIOD_MAP]
        available_score_counts = latest[score_columns].notna().sum(axis=1)
        latest["available_period_count"] = available_score_counts
        latest["period_average_score"] = latest[score_columns].mean(axis=1, skipna=True)
        latest["period_min_score"] = latest[score_columns].min(axis=1, skipna=True)
        latest["period_max_score"] = latest[score_columns].max(axis=1, skipna=True)
        latest["period_above_target_ratio"] = (
            latest[score_columns].ge(1).sum(axis=1) / available_score_counts.replace(0, pd.NA)
        )

        latest["previous_score"] = latest["summary_previous_score"].combine_first(latest["history_previous_score"])
        latest["change_vs_previous"] = latest["selected_score"] - latest["previous_score"]
        latest["change_vs_previous"] = latest["change_vs_previous"].combine_first(latest["history_change_vs_previous"])
        latest["below_target_streak"] = latest["history_below_target_streak"].fillna(0).astype(int)
        latest["recent_decline_flag"] = latest["history_recent_decline_flag"].fillna(False).astype(bool)
        latest["recent_trend"] = latest["selected_score"] - latest["recent_start_score"]
        latest["recent_trend"] = latest["recent_trend"].fillna(latest["change_vs_previous"])
        latest["recent_observation_count"] = latest["recent_observation_count"].fillna(0).astype(int)
        latest["recent_above_target_ratio"] = latest["recent_above_target_ratio"].fillna(0.0)
        latest["recent_volatility"] = latest["recent_std_score"].fillna(0.0)

        latest_global_date = latest["as_of_date"].max()
        latest["stale_metric"] = latest["as_of_date"] < (
            latest_global_date - pd.Timedelta(days=self.settings.stale_metric_threshold_days)
        )

        classification = latest.apply(self._classify_metric_alert, axis=1)
        latest["severity"] = classification.map(lambda item: item[0])
        latest["alert_reasons"] = classification.map(lambda item: item[1])

        normalized_trend = (1 + latest["recent_trend"].fillna(0).clip(lower=-0.5, upper=0.5)).clip(lower=0)
        latest["performance_index"] = (
            latest["selected_score"].fillna(0) * 0.5
            + latest["period_average_score"].fillna(0) * 0.25
            + normalized_trend * 0.15
            + latest["period_above_target_ratio"].fillna(0) * 0.10
        )
        latest["priority_index"] = (
            (1 - latest["selected_score"].fillna(1).clip(upper=1)) * 0.45
            + (-latest["recent_trend"].fillna(0).clip(upper=0)) * 0.20
            + (1 - latest["period_above_target_ratio"].fillna(0)) * 0.20
            + latest["below_target_streak"].clip(upper=5).fillna(0) / 5 * 0.10
            + latest["severity"].map({"red": 0.15, "amber": 0.08, "blue": 0.06, "green": 0.0}).fillna(0)
        )
        latest["consulting_bucket"] = latest.apply(self._classify_consulting_bucket, axis=1)
        latest["severity_rank"] = latest["severity"].map(SEVERITY_RANK)
        latest["selected_score_sort"] = latest["selected_score"].fillna(999.0)

        return latest.sort_values(["severity_rank", "service_area_order", "display_name"]).reset_index(drop=True)

    def _build_alerts(self, latest_metric_snapshot: pd.DataFrame) -> pd.DataFrame:
        alerts = latest_metric_snapshot[latest_metric_snapshot["severity"] != "green"].copy()
        return alerts.sort_values(
            ["severity_rank", "selected_score_sort", "display_name"],
            ascending=[True, True, True],
        ).reset_index(drop=True)

    def _build_service_area_summary(self, latest_metric_snapshot: pd.DataFrame) -> pd.DataFrame:
        grouped = latest_metric_snapshot.groupby("service_area", as_index=False).agg(
            metric_count=("metric_name", "count"),
            selected_score_average=("selected_score", "mean"),
            day_score_average=("day_score", "mean"),
            week_score_average=("week_score", "mean"),
            month_score_average=("month_score", "mean"),
            quarter_score_average=("quarter_score", "mean"),
        )

        severity_counts = pd.crosstab(latest_metric_snapshot["service_area"], latest_metric_snapshot["severity"])
        for severity in ["red", "amber", "blue", "green"]:
            if severity not in severity_counts.columns:
                severity_counts[severity] = 0

        summary = grouped.merge(
            severity_counts[["red", "amber", "blue", "green"]].reset_index(),
            on="service_area",
            how="left",
        )
        summary = summary.rename(
            columns={
                "red": "red_count",
                "amber": "amber_count",
                "blue": "blue_count",
                "green": "green_count",
            }
        )
        summary["service_area_order"] = summary["service_area"].map(self._service_area_order)
        return summary.sort_values(["service_area_order", "service_area"]).reset_index(drop=True)

    def _build_recent_selected_period_summary(self, metric_history_long: pd.DataFrame) -> pd.DataFrame:
        current_history = metric_history_long[metric_history_long["source"] == "current_full_snapshot"].copy()
        if current_history.empty:
            return pd.DataFrame(
                columns=[
                    "metric_name",
                    "selected_period",
                    "recent_observation_count",
                    "recent_start_score",
                    "recent_end_score",
                    "recent_mean_score",
                    "recent_min_score",
                    "recent_max_score",
                    "recent_std_score",
                    "recent_above_target_ratio",
                ]
            )

        current_history["is_above_target"] = current_history["score"] >= 1
        summary = (
            current_history.sort_values(["metric_name", "period_type", "as_of_date"])
            .groupby(["metric_name", "period_type"], as_index=False)
            .agg(
                recent_observation_count=("score", "count"),
                recent_start_score=("score", "first"),
                recent_end_score=("score", "last"),
                recent_mean_score=("score", "mean"),
                recent_min_score=("score", "min"),
                recent_max_score=("score", "max"),
                recent_std_score=("score", "std"),
                recent_above_target_ratio=("is_above_target", "mean"),
            )
            .rename(columns={"period_type": "selected_period"})
        )
        return summary

    def _build_executive_brief_payload(
        self,
        cleaned_frames: dict[str, pd.DataFrame],
        latest_metric_snapshot: pd.DataFrame,
        service_area_summary: pd.DataFrame,
        freshness: dict[str, Any],
    ) -> dict[str, Any]:
        scoped_metrics = latest_metric_snapshot.copy()
        ranked_metrics = scoped_metrics[scoped_metrics["selected_score"].notna()].copy()
        composite_ranked = scoped_metrics[scoped_metrics["composite_score"].notna()].copy()
        portfolio_health = self._build_portfolio_health_summary(composite_ranked)

        above_target_rate = float((ranked_metrics["selected_score"] >= 1).mean()) if not ranked_metrics.empty else 0.0
        median_score = float(ranked_metrics["selected_score"].median()) if not ranked_metrics.empty else 0.0
        priority_intervention_count = int((scoped_metrics["consulting_bucket"] == "Priority Intervention").sum())

        health_verdict = portfolio_health["verdict"]
        if health_verdict == "HEALTHY":
            headline_status = "healthy"
            headline_text = "Boston's service portfolio appears generally healthy, with most scored services above target."
        elif health_verdict == "MIXED":
            headline_status = "mixed"
            headline_text = "Boston's service portfolio is mixed: core services are functioning, but several priorities need leadership attention."
        else:
            headline_status = "concerning"
            headline_text = "Boston's service portfolio is concerning: too many services are below target or deteriorating."

        best_services = ranked_metrics.sort_values(
            ["performance_index", "selected_score", "display_name"],
            ascending=[False, False, True],
        ).head(5)
        worst_services = ranked_metrics.sort_values(
            ["priority_index", "selected_score", "display_name"],
            ascending=[False, True, True],
        ).head(5)
        composite_leaders = (
            composite_ranked[~composite_ranked["metric_name"].isin(NOTEBOOK_TOP_EXCLUSIONS)]
            .sort_values(["composite_score", "display_name"], ascending=[False, True])
            .head(5)
            .reset_index(drop=True)
        )
        composite_laggards = composite_ranked.sort_values(
            ["composite_score", "display_name"], ascending=[True, True]
        ).head(5)
        ranked_service_table = composite_ranked.sort_values(
            ["composite_score", "display_name"], ascending=[True, True]
        ).reset_index(drop=True)

        strongest_service_area = (
            service_area_summary.sort_values("selected_score_average", ascending=False).iloc[0]["service_area"]
            if not service_area_summary.empty
            else "Unassigned"
        )
        weakest_service_area = (
            service_area_summary.sort_values("selected_score_average", ascending=True).iloc[0]["service_area"]
            if not service_area_summary.empty
            else "Unassigned"
        )

        supporting_text = (
            f"{above_target_rate:.0%} of scored services are above target, with {priority_intervention_count} "
            f"services in priority intervention. Strength is most visible in {strongest_service_area}, while "
            f"{weakest_service_area} needs the closest managerial follow-up."
        )

        current_full_file = self.settings.raw_files["current_full_metrics"]
        current_full_frame = cleaned_frames["current_full_metrics"]
        analysis_start = self._safe_date_value(current_full_frame["score_calculated_ts"].min())
        analysis_end = self._safe_date_value(current_full_frame["score_calculated_ts"].max())
        download_date = datetime.fromtimestamp(current_full_file.stat().st_mtime).date()
        snapshot_dates = int(current_full_frame["score_calculated_ts"].dt.normalize().nunique())

        data_scope = {
            "source_focus": "CityScore Full Metric List",
            "download_date": download_date,
            "analysis_start_date": analysis_start,
            "analysis_end_date": analysis_end,
            "services_in_scope": int(len(scoped_metrics)),
            "services_ranked": int(len(ranked_metrics)),
            "snapshot_dates": snapshot_dates,
            "reading_note": "CityScore values below 1 indicate performance below target; values above 1 indicate performance above target.",
        }

        portfolio_mix = {
            bucket: int((scoped_metrics["consulting_bucket"] == bucket).sum())
            for bucket in ["Leading", "Stable", "Watchlist", "Priority Intervention", "Data Gap"]
        }
        performance_bands = self._build_performance_band_summary(composite_ranked)
        trend_distribution = self._build_trend_distribution(composite_ranked)
        department_summary = self._build_department_summary(scoped_metrics)

        kpi_cards = [
            {
                "label": "Portfolio Health Score",
                "value": f"{portfolio_health['score']:.0f}",
                "detail": f"{portfolio_health['verdict'].title()} on the notebook-style 0–100 consulting scale",
            },
            {
                "label": "Services Above Target",
                "value": f"{above_target_rate:.0%}",
                "detail": f"{int((ranked_metrics['selected_score'] >= 1).sum())} of {len(ranked_metrics)} scored services",
            },
            {
                "label": "Median CityScore",
                "value": f"{median_score:.2f}",
                "detail": "Median latest available service score",
            },
            {
                "label": "Priority Interventions",
                "value": str(priority_intervention_count),
                "detail": "Services classified as requiring immediate leadership attention",
            },
        ]

        methodology = [
            {
                "title": "Latest score anchors the diagnosis",
                "description": "Each service starts with its latest available CityScore from the Full Metric List. Scores below 1 are below target and scores above 1 exceed target.",
            },
            {
                "title": "Composite score preserves the notebook logic",
                "description": "The notebook-style composite score prefers quarter, then month, then week, so leadership rankings are not dominated by the shortest horizon when longer-period evidence exists.",
            },
            {
                "title": "Best performers use more than one snapshot",
                "description": "Best-service ranking blends the latest score, the average across available day/week/month/quarter views, and the recent trend across the Full Metric List snapshots.",
            },
            {
                "title": "Worst performers combine level and momentum",
                "description": "Worst-service ranking blends target gap, negative recent trend, weak consistency across periods, and the existing alert severity logic.",
            },
            {
                "title": "Missing services are tracked separately",
                "description": "Metrics without a current score are excluded from best/worst ranking and shown as data gaps so the Mayor does not confuse missing data with poor performance.",
            },
            {
                "title": "Performance bands stay transparent",
                "description": "The dashboard carries the notebook thresholds directly: Critical below 0.70, At Risk from 0.70 to 0.89, Near Miss from 0.90 to 0.99, On Target from 1.00 to 1.09, and Exceeding at 1.10 or above.",
            },
            {
                "title": "Composite leaders preserve the notebook exclusion rule",
                "description": "The notebook-style composite top 5 excludes Homicides, Shootings, and Library Users so the operational standout list is not dominated by extreme trend outliers.",
            },
        ]

        recommendations = self._build_recommendations(
            scoped_metrics=scoped_metrics,
            best_services=best_services,
            worst_services=worst_services,
            freshness=freshness,
        )

        return {
            "headline_status": headline_status,
            "headline_text": headline_text,
            "supporting_text": supporting_text,
            "kpi_cards": kpi_cards,
            "data_scope": data_scope,
            "score_guide": [
                "Use 1.0 as the decision boundary: scores below 1 are below target and scores above 1 exceed target.",
                "The dashboard focuses on the CityScore Full Metric List and uses multiple recent snapshots to reduce one-day ranking bias.",
                "Priority Intervention metrics combine poor current performance with negative recent movement or weak consistency across periods.",
                "Composite score views preserve the notebook method by preferring quarter, then month, then week.",
            ],
            "portfolio_health": portfolio_health,
            "portfolio_mix": portfolio_mix,
            "performance_bands": performance_bands,
            "trend_distribution": trend_distribution,
            "department_summary": department_summary,
            "best_services": [
                self._ranked_service_record(row, rank=index + 1, ranking_score_column="performance_index", mode="best")
                for index, (_, row) in enumerate(best_services.iterrows())
            ],
            "worst_services": [
                self._ranked_service_record(row, rank=index + 1, ranking_score_column="priority_index", mode="worst")
                for index, (_, row) in enumerate(worst_services.iterrows())
            ],
            "composite_leaders": [
                self._ranked_service_record(row, rank=index + 1, ranking_score_column="composite_score", mode="best")
                for index, (_, row) in enumerate(composite_leaders.iterrows())
            ],
            "composite_laggards": [
                self._ranked_service_record(row, rank=index + 1, ranking_score_column="composite_score", mode="worst")
                for index, (_, row) in enumerate(composite_laggards.iterrows())
            ],
            "ranked_service_table": [
                self._ranked_service_record(row, rank=index + 1, ranking_score_column="composite_score", mode="ranked")
                for index, (_, row) in enumerate(ranked_service_table.iterrows())
            ],
            "methodology": methodology,
            "recommendations": recommendations,
        }

    def _classify_consulting_bucket(self, row: pd.Series) -> str:
        current_score = row.get("selected_score")
        recent_trend = row.get("recent_trend")
        consistency = row.get("period_above_target_ratio")
        severity = row.get("severity")

        if pd.isna(current_score) or severity == "blue":
            return "Data Gap"
        if severity == "red" or (
            current_score < 1.0
            and (self._safe_float_value(recent_trend) or 0.0) < 0
            and (self._safe_float_value(consistency) or 0.0) < 0.5
        ):
            return "Priority Intervention"
        if current_score >= 1.05 and (self._safe_float_value(recent_trend) or 0.0) >= 0 and (
            self._safe_float_value(consistency) or 0.0
        ) >= 0.75:
            return "Leading"
        if current_score >= 1.0 and (self._safe_float_value(consistency) or 0.0) >= 0.5:
            return "Stable"
        return "Watchlist"

    def _ranked_service_record(
        self,
        row: pd.Series,
        rank: int | None,
        ranking_score_column: str,
        mode: str,
    ) -> dict[str, Any]:
        current_score = self._safe_float_value(row.get("selected_score"))
        previous_score = self._safe_float_value(row.get("previous_score"))
        recent_trend = self._safe_float_value(row.get("recent_trend"))
        period_average = self._safe_float_value(row.get("period_average_score"))
        above_target_ratio = self._safe_float_value(row.get("period_above_target_ratio"))
        selected_period = self._safe_period_value(row.get("selected_period"))
        composite_score = self._safe_float_value(row.get("composite_score"))
        evidence_parts: list[str] = []

        if mode == "best":
            if current_score is not None:
                evidence_parts.append(f"Latest {selected_period or 'available'} score is {current_score:.2f}.")
            if period_average is not None:
                evidence_parts.append(f"Cross-period average is {period_average:.2f}.")
            if recent_trend is not None:
                evidence_parts.append(
                    "Recent snapshots are improving."
                    if recent_trend >= 0
                    else "Recent snapshots have softened slightly."
                )
            if above_target_ratio is not None:
                evidence_parts.append(f"{above_target_ratio:.0%} of available period views are above target.")
        else:
            if current_score is not None:
                evidence_parts.append(f"Latest {selected_period or 'available'} score is {current_score:.2f}.")
            if current_score is not None and current_score < 1:
                evidence_parts.append(f"That is {1 - current_score:.2f} points below the CityScore threshold.")
            if recent_trend is not None and recent_trend < 0:
                evidence_parts.append(f"Recent snapshots declined by {abs(recent_trend):.2f} points.")
            if above_target_ratio is not None:
                evidence_parts.append(f"Only {above_target_ratio:.0%} of available period views are above target.")
            if mode == "ranked" and composite_score is not None:
                evidence_parts.append(f"Composite score is {composite_score:.2f}.")

        return {
            "rank": rank,
            "metric_name": row["metric_name"],
            "display_name": row["display_name"],
            "service_area": row["service_area"],
            "owner_department": row["owner_department"],
            "department": self._safe_text_value(row.get("department")),
            "classification": self._safe_text_value(row.get("consulting_bucket")) or "Unclassified",
            "selected_period": selected_period,
            "current_score": current_score,
            "previous_score": previous_score,
            "recent_trend": recent_trend,
            "period_average_score": period_average,
            "period_above_target_ratio": above_target_ratio,
            "ranking_score": self._safe_float_value(row.get(ranking_score_column)),
            "target": self._safe_float_value(row.get("target")),
            "composite_score": composite_score,
            "gap_to_target": self._safe_float_value(row.get("gap_to_target")),
            "day_score_final": self._safe_float_value(row.get("day_score_final")),
            "trend_delta_dw": self._safe_float_value(row.get("trend_delta_dw")),
            "trend_delta_wq": self._safe_float_value(row.get("trend_delta_wq")),
            "trend_delta_mq": self._safe_float_value(row.get("trend_delta_mq")),
            "trend_label": self._safe_text_value(row.get("trend_label")),
            "perf_band": self._safe_text_value(row.get("perf_band")),
            "evidence": " ".join(evidence_parts) if evidence_parts else "Evidence unavailable.",
        }

    def _build_recommendations(
        self,
        scoped_metrics: pd.DataFrame,
        best_services: pd.DataFrame,
        worst_services: pd.DataFrame,
        freshness: dict[str, Any],
    ) -> list[dict[str, Any]]:
        recommendations: list[dict[str, Any]] = []

        if not worst_services.empty:
            top_issue = worst_services.iloc[0]
            recommendations.append(
                {
                    "priority": "Immediate",
                    "action_title": f"Stabilize {top_issue['display_name']}",
                    "owner": top_issue["owner_department"],
                    "service_area": top_issue["service_area"],
                    "evidence": self._ranked_service_record(top_issue, rank=1, ranking_score_column="priority_index", mode="worst")["evidence"],
                    "recommendation": self._service_recovery_recommendation(top_issue),
                    "next_step": "Ask the department head for a short recovery plan with staffing, backlog, and operational bottlenecks before the next cabinet review.",
                }
            )

        if len(worst_services) > 1:
            watchlist_slice = worst_services.head(3)
            weakest_area = (
                watchlist_slice["service_area"].mode().iloc[0]
                if not watchlist_slice["service_area"].mode().empty
                else watchlist_slice.iloc[0]["service_area"]
            )
            watchlist_names = ", ".join(watchlist_slice["display_name"].tolist())
            recommendations.append(
                {
                    "priority": "High",
                    "action_title": f"Run a targeted watchlist review for {weakest_area}",
                    "owner": "Mayor's Office / Chief of Staff",
                    "service_area": weakest_area,
                    "evidence": f"The current bottom tier includes {watchlist_names}, pointing to concentrated pressure in {weakest_area}.",
                    "recommendation": "Hold a cross-functional operating review that compares demand, staffing, and service-cycle performance across the weakest metrics in this area.",
                    "next_step": "Use the metric drill-downs to confirm whether the issue is a one-snapshot dip or a repeated multi-period pattern.",
                }
            )

        if not best_services.empty:
            exemplar = best_services.iloc[0]
            recommendations.append(
                {
                    "priority": "Medium",
                    "action_title": f"Replicate practices from {exemplar['display_name']}",
                    "owner": exemplar["owner_department"],
                    "service_area": exemplar["service_area"],
                    "evidence": self._ranked_service_record(exemplar, rank=1, ranking_score_column="performance_index", mode="best")["evidence"],
                    "recommendation": "Document the operating practices behind this service's performance and test whether those habits can transfer to weaker services in the same or adjacent service areas.",
                    "next_step": "Ask the owning department to share the specific staffing, routing, queue-management, or quality-control practice behind the current result.",
                }
            )

        if freshness.get("metrics_missing_selected_score", 0) > 0 or freshness.get("stale_metrics", 0) > 0:
            recommendations.append(
                {
                    "priority": "Medium",
                    "action_title": "Close data freshness gaps before the briefing cycle",
                    "owner": "Analytics Team",
                    "service_area": "Citywide",
                    "evidence": (
                        f"{freshness.get('metrics_missing_selected_score', 0)} metrics are missing a current selected score "
                        f"and {freshness.get('stale_metrics', 0)} are stale."
                    ),
                    "recommendation": "Separate data delays from true service underperformance so the Mayor is not reacting to missing feeds as if they were operational failures.",
                    "next_step": "Confirm metric cadence expectations and add source-specific escalation for late or incomplete daily loads.",
                }
            )

        if not recommendations:
            recommendations.append(
                {
                    "priority": "Monitor",
                    "action_title": "Maintain current operating cadence",
                    "owner": "Mayor's Office / Analytics Team",
                    "service_area": "Citywide",
                    "evidence": "No concentrated intervention signals were detected in the latest ranked snapshot.",
                    "recommendation": "Continue monitoring the portfolio and preserve the current briefing rhythm to catch changes early.",
                    "next_step": "Review the next daily refresh for any movement into watchlist or priority-intervention status.",
                }
            )

        return recommendations[:5]

    def _service_recovery_recommendation(self, row: pd.Series) -> str:
        metric_name = str(row.get("metric_name", ""))
        service_area = str(row.get("service_area", ""))
        if "RESPONSE TIME" in metric_name:
            return "Investigate dispatch, routing, and staffing coverage to reduce response-time slippage and restore threshold performance."
        if "ON-TIME" in metric_name or "PERMIT" in metric_name:
            return "Review queue age, staffing allocation, and handoff delays to recover on-time service performance."
        if "INCIDENTS" in metric_name or "CRIMES" in metric_name or "HOMICIDES" in metric_name or "SHOOTINGS" in metric_name or "STABBINGS" in metric_name:
            return "Pair the score drop with operational context and ask leadership to explain whether the increase reflects a temporary spike or a broader public-safety pattern."
        if service_area == "Resident Experience":
            return "Check response workflows, closure practices, and resident follow-up to recover constituent-facing service quality."
        return "Run a focused service recovery review to isolate the operational drivers behind the below-target score and assign corrective actions."

    def _build_freshness_payload(
        self,
        dataset_status: list[dict[str, Any]],
        latest_metric_snapshot: pd.DataFrame,
    ) -> dict[str, Any]:
        coverage = (
            latest_metric_snapshot.groupby("service_area", as_index=False).agg(
                total_metrics=("metric_name", "count"),
                metrics_with_selected_score=("selected_score", lambda scores: int(scores.notna().sum())),
                metrics_missing_day_score=("day_score", lambda scores: int(scores.isna().sum())),
                actionable_alerts=("severity", lambda items: int(items.isin(["red", "amber", "blue"]).sum())),
            )
        )
        coverage["service_area_order"] = coverage["service_area"].map(self._service_area_order)
        coverage = coverage.sort_values(["service_area_order", "service_area"])

        return {
            "as_of_date": self._safe_date_value(latest_metric_snapshot["as_of_date"].max()),
            "metrics_total": int(len(latest_metric_snapshot)),
            "metrics_with_day_score": int(latest_metric_snapshot["day_score"].notna().sum()),
            "metrics_missing_day_score": int(latest_metric_snapshot["day_score"].isna().sum()),
            "metrics_with_selected_score": int(latest_metric_snapshot["selected_score"].notna().sum()),
            "metrics_missing_selected_score": int(latest_metric_snapshot["selected_score"].isna().sum()),
            "stale_metrics": int(latest_metric_snapshot["stale_metric"].fillna(False).sum()),
            "actionable_alerts": int(latest_metric_snapshot["severity"].isin(["red", "amber", "blue"]).sum()),
            "datasets": dataset_status,
            "coverage_by_service_area": [
                {
                    "service_area": row["service_area"],
                    "total_metrics": int(row["total_metrics"]),
                    "metrics_with_selected_score": int(row["metrics_with_selected_score"]),
                    "metrics_missing_day_score": int(row["metrics_missing_day_score"]),
                    "actionable_alerts": int(row["actionable_alerts"]),
                }
                for _, row in coverage.iterrows()
            ],
        }

    def _build_mayor_daily_brief_payload(
        self,
        city_score_history: pd.DataFrame,
        latest_metric_snapshot: pd.DataFrame,
        alerts: pd.DataFrame,
        service_area_summary: pd.DataFrame,
        freshness: dict[str, Any],
    ) -> dict[str, Any]:
        top_cards = []
        for period_type in ["day", "week", "month", "quarter"]:
            period_history = city_score_history[city_score_history["period_type"] == period_type]
            if period_history.empty:
                top_cards.append(
                    {
                        "period_type": period_type,
                        "score": None,
                        "previous_score": None,
                        "change": None,
                        "status": "blue",
                    }
                )
                continue

            latest_row = period_history.sort_values("as_of_date").iloc[-1]
            top_cards.append(
                {
                    "period_type": period_type,
                    "score": self._safe_float_value(latest_row["score"]),
                    "previous_score": self._safe_float_value(latest_row["previous_score"]),
                    "change": self._safe_float_value(latest_row["change"]),
                    "status": self._score_to_severity(latest_row["score"]),
                }
            )

        critical_alerts = [
            self._alert_record(row)
            for _, row in alerts.head(self.settings.top_alert_limit).iterrows()
        ]

        if latest_metric_snapshot.empty:
            change_summary = {
                "improving_metrics": 0,
                "worsening_metrics": 0,
                "stable_or_missing_metrics": 0,
                "below_target_metrics": 0,
            }
        else:
            change_summary = {
                "improving_metrics": int((latest_metric_snapshot["change_vs_previous"] > 0).sum()),
                "worsening_metrics": int((latest_metric_snapshot["change_vs_previous"] < 0).sum()),
                "stable_or_missing_metrics": int(latest_metric_snapshot["change_vs_previous"].isna().sum())
                + int((latest_metric_snapshot["change_vs_previous"] == 0).sum()),
                "below_target_metrics": int((latest_metric_snapshot["selected_score"] < 1).sum()),
            }

        return {
            "as_of_date": freshness["as_of_date"],
            "note": (
                "Daily scores reflect the previous weekday, weekly scores the previous 7 days, "
                "monthly scores the rolling previous month, and quarterly scores the rolling previous quarter."
            ),
            "top_cards": top_cards,
            "critical_alerts": critical_alerts,
            "service_area_scorecards": [
                self._service_area_record(row) for _, row in service_area_summary.iterrows()
            ],
            "change_summary": change_summary,
            "data_freshness": freshness,
        }

    def _write_cleaned_outputs(self, cleaned_frames: dict[str, pd.DataFrame]) -> None:
        file_map = {
            "current_full_metrics": "current_full_metrics_clean.csv",
            "current_summary": "current_summary_clean.csv",
            "historical_city_agg": "historical_city_agg_clean.csv",
            "historical_metric_summary": "historical_metric_summary_clean.csv",
        }
        for dataset_name, filename in file_map.items():
            self._write_frame(cleaned_frames[dataset_name], self.settings.cleaned_dir / filename)

    def _write_aggregated_outputs(
        self,
        metric_master: pd.DataFrame,
        metric_history_long: pd.DataFrame,
        city_score_history: pd.DataFrame,
        latest_metric_snapshot: pd.DataFrame,
        alerts: pd.DataFrame,
        service_area_summary: pd.DataFrame,
        executive_brief: dict[str, Any],
    ) -> None:
        self._write_frame(metric_master, self.settings.aggregated_dir / "metric_master.csv")
        self._write_frame(metric_history_long, self.settings.aggregated_dir / "metric_history_long.csv")
        self._write_frame(city_score_history, self.settings.aggregated_dir / "city_score_history.csv")
        self._write_frame(latest_metric_snapshot, self.settings.aggregated_dir / "latest_metric_snapshot.csv")
        self._write_frame(alerts, self.settings.aggregated_dir / "mayor_alerts.csv")
        self._write_frame(service_area_summary, self.settings.aggregated_dir / "service_area_summary.csv")
        (self.settings.aggregated_dir / "executive_brief.json").write_text(
            json.dumps(executive_brief, indent=2, default=str),
            encoding="utf-8",
        )

    def _write_frame(self, frame: pd.DataFrame, output_path: Path) -> None:
        serializable = frame.copy()
        for column in serializable.columns:
            if pd.api.types.is_datetime64_any_dtype(serializable[column]):
                serializable[column] = serializable[column].dt.strftime("%Y-%m-%d %H:%M:%S")
        serializable.to_csv(output_path, index=False)

    def _service_area_record(self, row: pd.Series) -> dict[str, Any]:
        return {
            "service_area": row["service_area"],
            "metric_count": int(row["metric_count"]),
            "selected_score_average": self._safe_float_value(row.get("selected_score_average")),
            "day_score_average": self._safe_float_value(row.get("day_score_average")),
            "week_score_average": self._safe_float_value(row.get("week_score_average")),
            "month_score_average": self._safe_float_value(row.get("month_score_average")),
            "quarter_score_average": self._safe_float_value(row.get("quarter_score_average")),
            "red_count": int(row.get("red_count", 0)),
            "amber_count": int(row.get("amber_count", 0)),
            "blue_count": int(row.get("blue_count", 0)),
            "green_count": int(row.get("green_count", 0)),
        }

    def _alert_record(self, row: pd.Series) -> dict[str, Any]:
        return {
            "metric_name": row["metric_name"],
            "display_name": row["display_name"],
            "service_area": row["service_area"],
            "owner_department": row["owner_department"],
            "selected_period": self._safe_period_value(row.get("selected_period")),
            "current_score": self._safe_float_value(row.get("selected_score")),
            "previous_score": self._safe_float_value(row.get("previous_score")),
            "change_vs_previous": self._safe_float_value(row.get("change_vs_previous")),
            "rolling_mean_14": self._safe_float_value(row.get("rolling_mean_14")),
            "rolling_mean_28": self._safe_float_value(row.get("rolling_mean_28")),
            "below_target_streak": int(row.get("below_target_streak", 0)),
            "target": self._safe_float_value(row.get("target")),
            "actual_primary_value": self._safe_float_value(row.get("actual_primary_value")),
            "actual_secondary_value": self._safe_float_value(row.get("actual_secondary_value")),
            "severity": row["severity"],
            "alert_reasons": row["alert_reasons"],
            "as_of_date": self._safe_date_value(row.get("as_of_date")),
        }

    def _metric_summary_record(self, row: pd.Series) -> dict[str, Any]:
        return {
            "metric_name": row["metric_name"],
            "display_name": row["display_name"],
            "service_area": row["service_area"],
            "owner_department": row["owner_department"],
            "department": self._safe_text_value(row.get("department")),
            "cadence": row["cadence"],
            "definition": row["definition"],
            "metric_logic": self._safe_text_value(row.get("metric_logic")),
            "target": self._safe_float_value(row.get("target")),
            "selected_period": self._safe_period_value(row.get("selected_period")),
            "current_score": self._safe_float_value(row.get("selected_score")),
            "previous_score": self._safe_float_value(row.get("previous_score")),
            "change_vs_previous": self._safe_float_value(row.get("change_vs_previous")),
            "rolling_mean_14": self._safe_float_value(row.get("rolling_mean_14")),
            "rolling_mean_28": self._safe_float_value(row.get("rolling_mean_28")),
            "consulting_bucket": self._safe_text_value(row.get("consulting_bucket")),
            "performance_index": self._safe_float_value(row.get("performance_index")),
            "priority_index": self._safe_float_value(row.get("priority_index")),
            "composite_score": self._safe_float_value(row.get("composite_score")),
            "gap_to_target": self._safe_float_value(row.get("gap_to_target")),
            "day_score_final": self._safe_float_value(row.get("day_score_final")),
            "trend_delta_dw": self._safe_float_value(row.get("trend_delta_dw")),
            "trend_delta_wq": self._safe_float_value(row.get("trend_delta_wq")),
            "trend_delta_mq": self._safe_float_value(row.get("trend_delta_mq")),
            "trend_label": self._safe_text_value(row.get("trend_label")),
            "perf_band": self._safe_text_value(row.get("perf_band")),
            "severity": row["severity"],
            "alert_reasons": row["alert_reasons"],
            "as_of_date": self._safe_date_value(row.get("as_of_date")),
        }

    def _history_record(self, row: pd.Series) -> dict[str, Any]:
        return {
            "metric_name": row["metric_name"],
            "display_name": row["display_name"],
            "period_type": row["period_type"],
            "as_of_date": self._safe_date_value(row["as_of_date"]),
            "score": self._safe_float_value(row.get("score")),
            "previous_score": self._safe_float_value(row.get("previous_score")),
            "change_vs_previous": self._safe_float_value(row.get("change_vs_previous")),
            "rolling_mean_14": self._safe_float_value(row.get("rolling_mean_14")),
            "rolling_mean_28": self._safe_float_value(row.get("rolling_mean_28")),
            "below_target_streak": int(row.get("below_target_streak", 0)),
            "actual_primary_value": self._safe_float_value(row.get("actual_primary_value")),
            "actual_secondary_value": self._safe_float_value(row.get("actual_secondary_value")),
            "target": self._safe_float_value(row.get("target")),
            "source": row["source"],
        }

    def _pick_selected_period(self, row: pd.Series) -> str | None:
        for period_type in ["day", "week", "month", "quarter"]:
            if pd.notna(row.get(f"{period_type}_score")):
                return period_type
        return None

    def _extract_period_value(self, row: pd.Series, period_type: str | None, suffix: str) -> float | None:
        if not isinstance(period_type, str) or not period_type:
            return None
        column_name = f"{period_type}_{suffix}"
        return row.get(column_name)

    def _extract_summary_previous_score(self, row: pd.Series) -> float | None:
        period_type = row.get("selected_period")
        if not isinstance(period_type, str) or not period_type:
            return None
        previous_column = CURRENT_SUMMARY_PREVIOUS_MAP[period_type]
        return row.get(previous_column)

    def _classify_metric_alert(self, row: pd.Series) -> tuple[str, list[str]]:
        reasons: list[str] = []
        current_score = row.get("selected_score")
        rolling_mean_14 = row.get("rolling_mean_14")
        below_target_streak = int(row.get("below_target_streak", 0) or 0)
        recent_decline_flag = bool(row.get("recent_decline_flag", False))
        stale_metric = bool(row.get("stale_metric", False))

        if stale_metric:
            reasons.append("Metric is stale relative to the latest available snapshot.")
            return "blue", reasons
        if pd.isna(current_score):
            reasons.append("No current score is available for the selected period.")
            return "blue", reasons

        below_target = current_score < 1.0
        severe_baseline_gap = False
        moderate_baseline_gap = False

        if below_target:
            reasons.append("Current score is below the CityScore target threshold of 1.0.")

        if pd.notna(rolling_mean_14):
            if current_score < rolling_mean_14 - 0.10:
                severe_baseline_gap = True
                reasons.append("Current score is materially below the 14-observation rolling baseline.")
            elif current_score < rolling_mean_14 - 0.05:
                moderate_baseline_gap = True
                reasons.append("Current score is below the recent rolling baseline.")

        if below_target_streak >= 3:
            reasons.append(f"Metric has stayed below target for {below_target_streak} consecutive updates.")

        if recent_decline_flag:
            reasons.append("Recent observations show a consecutive decline.")

        if below_target and (current_score < 0.90 or severe_baseline_gap or below_target_streak >= 3):
            return "red", reasons
        if below_target or moderate_baseline_gap or recent_decline_flag:
            return "amber", reasons
        return "green", ["On track."]

    def _performance_band(self, score: float | None) -> str:
        if pd.isna(score):
            return "Unknown"
        score_value = float(score)
        for band, threshold, _ in PERFORMANCE_BAND_THRESHOLDS:
            if score_value < threshold:
                return band
        return "Unknown"

    def _trend_label(self, delta: float | None) -> str:
        if pd.isna(delta):
            return "Unknown"
        if float(delta) >= 0.05:
            return "Improving"
        if float(delta) <= -0.05:
            return "Deteriorating"
        return "Stable"

    def _categorize_department(self, metric_name: str | None) -> str:
        metric_name_lower = normalize_metric_name(metric_name).lower()
        if "library" in metric_name_lower:
            return "Library Department"
        if "bfd" in metric_name_lower:
            return "Fire Department (BFD)"
        if any(keyword in metric_name_lower for keyword in ["311", "city services satisfaction"]):
            return "City Services"
        if "ems" in metric_name_lower:
            return "Emergency Medical Services (EMS)"
        if "bps" in metric_name_lower:
            return "Boston Public Schools (BPS)"
        if any(keyword in metric_name_lower for keyword in ["homicides", "shootings", "stabbings", "part 1 crimes"]):
            return "Public Safety / Crime"
        if "signal repair" in metric_name_lower:
            return "Traffic Department"
        if "code enforcement" in metric_name_lower:
            return "Inspection Services Department"
        if any(
            keyword in metric_name_lower
            for keyword in ["graffiti", "trash", "pothole", "streetlight", "parks", "tree", "sign installation"]
        ):
            return "Public Works / Maintenance"
        if "permit" in metric_name_lower:
            return "Permitting Department"
        return "Other / Undefined"

    def _build_portfolio_health_summary(self, composite_ranked: pd.DataFrame) -> dict[str, Any]:
        total = int(len(composite_ranked))
        if total == 0:
            return {
                "score": 0.0,
                "verdict": "CONCERNING",
                "verdict_color": "#8f2c2c",
                "total_services": 0,
                "services_ranked": 0,
                "pass_rate_pct": 0.0,
                "below_target_pct": 0.0,
                "mean_score": None,
                "median_score": None,
                "components": [],
            }

        band_counts = composite_ranked["perf_band"].value_counts()
        trend_counts = composite_ranked["trend_label"].value_counts()

        n_critical = int(band_counts.get("CRITICAL", 0))
        n_atrisk = int(band_counts.get("AT RISK", 0))
        n_nearmiss = int(band_counts.get("NEAR MISS", 0))
        n_ontarget = int(band_counts.get("ON TARGET", 0))
        n_exceeding = int(band_counts.get("EXCEEDING", 0))

        n_improving = int(trend_counts.get("Improving", 0))
        n_deteriorating = int(trend_counts.get("Deteriorating", 0))
        n_below_target = n_critical + n_atrisk + n_nearmiss
        n_at_or_above = n_ontarget + n_exceeding

        mean_score = self._safe_float_value(composite_ranked["composite_score"].mean())
        median_score = self._safe_float_value(composite_ranked["composite_score"].median())
        pct_passing = n_at_or_above / total * 100
        pct_failing = n_below_target / total * 100

        component_1 = pct_passing * 0.40
        raw_penalty = (n_critical * 3 + n_atrisk * 1.5) / total * 10
        component_2 = min(raw_penalty, 30.0)
        net_trend = (n_improving - n_deteriorating) / total
        component_3 = (net_trend + 1) / 2 * 30
        health_score = max(0.0, min(100.0, component_1 - component_2 + component_3))

        if health_score >= 70:
            verdict = "HEALTHY"
            verdict_color = "#217346"
        elif health_score >= 45:
            verdict = "MIXED"
            verdict_color = "#C5941A"
        else:
            verdict = "CONCERNING"
            verdict_color = "#CC0000"

        return {
            "score": round(health_score, 1),
            "verdict": verdict,
            "verdict_color": verdict_color,
            "total_services": total,
            "services_ranked": total,
            "pass_rate_pct": round(pct_passing, 1),
            "below_target_pct": round(pct_failing, 1),
            "mean_score": mean_score,
            "median_score": median_score,
            "components": [
                {
                    "label": "Pass Rate",
                    "score": round(component_1, 1),
                    "detail": f"{n_at_or_above} of {total} services are on target or exceeding target.",
                },
                {
                    "label": "Severity Penalty",
                    "score": round(-component_2, 1),
                    "detail": f"{n_critical} critical and {n_atrisk} at-risk services create the penalty.",
                },
                {
                    "label": "Trend Momentum",
                    "score": round(component_3, 1),
                    "detail": f"{n_improving} services are improving versus {n_deteriorating} deteriorating.",
                },
            ],
        }

    def _build_performance_band_summary(self, composite_ranked: pd.DataFrame) -> list[dict[str, Any]]:
        total = int(len(composite_ranked)) or 1
        band_counts = composite_ranked["perf_band"].value_counts()
        return [
            {
                "band": band,
                "count": int(band_counts.get(band, 0)),
                "percentage": round(int(band_counts.get(band, 0)) / total * 100, 1),
                "threshold": threshold,
            }
            for band, _, threshold in PERFORMANCE_BAND_THRESHOLDS
        ]

    def _build_trend_distribution(self, composite_ranked: pd.DataFrame) -> list[dict[str, Any]]:
        total = int(len(composite_ranked)) or 1
        trend_counts = composite_ranked["trend_label"].value_counts()
        return [
            {
                "label": label,
                "count": int(trend_counts.get(label, 0)),
                "percentage": round(int(trend_counts.get(label, 0)) / total * 100, 1),
            }
            for label in ["Improving", "Stable", "Deteriorating", "Unknown"]
        ]

    def _build_department_summary(self, scoped_metrics: pd.DataFrame) -> list[dict[str, Any]]:
        summary = (
            scoped_metrics.groupby("department", as_index=False)
            .agg(
                metric_count=("metric_name", "count"),
                composite_score_average=("composite_score", "mean"),
                at_or_above_target_count=("composite_score", lambda scores: int((scores >= 1).sum())),
                below_target_count=("composite_score", lambda scores: int((scores < 1).sum())),
                priority_intervention_count=("consulting_bucket", lambda items: int((items == "Priority Intervention").sum())),
            )
            .sort_values(["composite_score_average", "metric_count"], ascending=[False, False])
        )
        return [
            {
                "department": row["department"],
                "metric_count": int(row["metric_count"]),
                "composite_score_average": self._safe_float_value(row.get("composite_score_average")),
                "at_or_above_target_count": int(row.get("at_or_above_target_count", 0)),
                "below_target_count": int(row.get("below_target_count", 0)),
                "priority_intervention_count": int(row.get("priority_intervention_count", 0)),
            }
            for _, row in summary.iterrows()
        ]

    def _score_to_severity(self, score: float | None) -> str:
        if pd.isna(score):
            return "blue"
        if score < 0.9:
            return "red"
        if score < 1.0:
            return "amber"
        return "green"

    def _service_area_order(self, service_area: str) -> int:
        try:
            return SERVICE_AREA_ORDER.index(service_area)
        except ValueError:
            return len(SERVICE_AREA_ORDER)

    def _snake_case_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        cleaned = df.copy()
        cleaned.columns = (
            cleaned.columns.astype(str)
            .str.strip()
            .str.lower()
            .str.replace("%", "pct", regex=False)
            .str.replace("/", "_", regex=False)
            .str.replace("(", "", regex=False)
            .str.replace(")", "", regex=False)
            .str.replace("-", "_", regex=False)
            .str.replace(" ", "_", regex=False)
            .str.replace(r"[^a-z0-9_]+", "", regex=True)
            .str.replace(r"_+", "_", regex=True)
            .str.strip("_")
        )
        return cleaned

    def _strip_text_values(self, df: pd.DataFrame) -> pd.DataFrame:
        cleaned = df.copy()
        object_columns = cleaned.select_dtypes(include=["object", "string"]).columns
        for column in object_columns:
            cleaned[column] = cleaned[column].astype("string").str.strip()
            cleaned[column] = cleaned[column].replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
        return cleaned

    def _drop_empty_rows_and_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        cleaned = df.dropna(how="all").copy()
        cleaned = cleaned.dropna(axis=1, how="all")
        return cleaned

    def _convert_excel_serial_dates(self, df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
        cleaned = df.copy()
        for column in columns:
            if column not in cleaned.columns:
                continue
            numeric_values = pd.to_numeric(cleaned[column], errors="coerce")
            excel_dates = pd.to_datetime(
                numeric_values,
                unit="D",
                origin="1899-12-30",
                errors="coerce",
            )
            parsed_dates = pd.to_datetime(cleaned[column], errors="coerce")
            cleaned[column] = excel_dates.where(excel_dates.notna(), parsed_dates)
        return cleaned

    def _coerce_numeric_columns(self, df: pd.DataFrame, skip_columns: set[str]) -> pd.DataFrame:
        cleaned = df.copy()
        for column in cleaned.columns:
            if column in skip_columns or pd.api.types.is_datetime64_any_dtype(cleaned[column]):
                continue
            numeric_values = pd.to_numeric(cleaned[column], errors="coerce")
            if numeric_values.notna().sum() > 0:
                cleaned[column] = numeric_values
        return cleaned

    def _compute_below_target_streak(self, scores: pd.Series) -> pd.Series:
        streaks: list[int] = []
        current_streak = 0
        for score in scores:
            if pd.notna(score) and score < 1.0:
                current_streak += 1
            else:
                current_streak = 0
            streaks.append(current_streak)
        return pd.Series(streaks, index=scores.index)

    def _compute_recent_decline_flag(self, scores: pd.Series) -> pd.Series:
        decline_flags: list[bool] = []
        history: list[float] = []
        for score in scores:
            if pd.notna(score):
                history.append(float(score))
            if len(history) >= 3 and history[-1] < history[-2] < history[-3]:
                decline_flags.append(True)
            else:
                decline_flags.append(False)
        return pd.Series(decline_flags, index=scores.index)

    def _safe_float_value(self, value: Any) -> float | None:
        if value is None or pd.isna(value):
            return None
        return float(value)

    def _safe_int_value(self, value: Any) -> int | None:
        if value is None or pd.isna(value):
            return None
        return int(value)

    def _safe_date_value(self, value: Any) -> date | None:
        if value is None or pd.isna(value):
            return None
        if isinstance(value, pd.Timestamp):
            return value.date()
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return pd.to_datetime(value).date()

    def _safe_datetime_string(self, value: Any) -> str | None:
        if value is None or pd.isna(value):
            return None
        if isinstance(value, pd.Timestamp):
            return value.isoformat()
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value)

    def _safe_period_value(self, value: Any) -> str | None:
        if value is None or pd.isna(value):
            return None
        return str(value)

    def _safe_text_value(self, value: Any) -> str | None:
        if value is None or pd.isna(value):
            return None
        return str(value)
