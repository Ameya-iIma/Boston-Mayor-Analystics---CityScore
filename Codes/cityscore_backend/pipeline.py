from __future__ import annotations

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

SEVERITY_RANK = {"red": 0, "amber": 1, "blue": 2, "green": 3}


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
    refreshed_at: datetime
    current_as_of_date: date | None


class CityScoreRepository:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.bundle: DataBundle | None = None
        self.last_refresh_error: str | None = None

    def ensure_ready(self) -> None:
        if self.bundle is None:
            self.refresh()

    def refresh(self, persist_outputs: bool = True) -> dict[str, Any]:
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

        if period_type:
            history = history[history["period_type"] == period_type.lower()]

        latest_as_of_date = history["as_of_date"].max()
        if pd.notna(latest_as_of_date):
            cutoff_date = latest_as_of_date - pd.Timedelta(days=days)
            history = history[history["as_of_date"] >= cutoff_date]

        history = history.sort_values(["period_type", "as_of_date"])
        return [self._history_record(row) for _, row in history.iterrows()]

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

        latest["previous_score"] = latest["summary_previous_score"].combine_first(latest["history_previous_score"])
        latest["change_vs_previous"] = latest["selected_score"] - latest["previous_score"]
        latest["change_vs_previous"] = latest["change_vs_previous"].combine_first(latest["history_change_vs_previous"])
        latest["below_target_streak"] = latest["history_below_target_streak"].fillna(0).astype(int)
        latest["recent_decline_flag"] = latest["history_recent_decline_flag"].fillna(False).astype(bool)

        latest_global_date = latest["as_of_date"].max()
        latest["stale_metric"] = latest["as_of_date"] < (latest_global_date - pd.Timedelta(days=self.settings.stale_metric_threshold_days))

        classification = latest.apply(self._classify_metric_alert, axis=1)
        latest["severity"] = classification.map(lambda item: item[0])
        latest["alert_reasons"] = classification.map(lambda item: item[1])
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
    ) -> None:
        self._write_frame(metric_master, self.settings.aggregated_dir / "metric_master.csv")
        self._write_frame(metric_history_long, self.settings.aggregated_dir / "metric_history_long.csv")
        self._write_frame(city_score_history, self.settings.aggregated_dir / "city_score_history.csv")
        self._write_frame(latest_metric_snapshot, self.settings.aggregated_dir / "latest_metric_snapshot.csv")
        self._write_frame(alerts, self.settings.aggregated_dir / "mayor_alerts.csv")
        self._write_frame(service_area_summary, self.settings.aggregated_dir / "service_area_summary.csv")

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
