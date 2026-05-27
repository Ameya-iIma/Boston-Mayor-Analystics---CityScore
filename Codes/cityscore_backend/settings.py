from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    project_root: Path = field(default_factory=lambda: Path(__file__).resolve().parents[1])
    rolling_windows: tuple[int, int] = (14, 28)
    top_alert_limit: int = 5
    stale_metric_threshold_days: int = 3
    is_vercel: bool = field(default_factory=lambda: bool(os.getenv("VERCEL") or os.getenv("VERCEL_ENV")))
    configured_data_dir: str | None = field(default_factory=lambda: os.getenv("CITYSCORE_DATA_DIR"))

    repo_root: Path = field(init=False)
    data_dir: Path = field(init=False)
    cleaned_dir: Path = field(init=False)
    aggregated_dir: Path = field(init=False)
    persist_outputs_default: bool = field(init=False)
    raw_files: dict[str, Path] = field(init=False)

    def __post_init__(self) -> None:
        app_root = self.project_root
        repo_root = app_root.parent if (app_root.parent / "Excel").exists() else app_root
        if self.configured_data_dir:
            data_dir = Path(self.configured_data_dir).expanduser().resolve()
        else:
            data_dir = app_root / "Excel" if (app_root / "Excel").exists() else repo_root / "Excel"
        output_root = Path("/tmp") if self.is_vercel else repo_root
        cleaned_dir = output_root / "cleaned csv"
        aggregated_dir = output_root / "aggregated data"
        raw_files = {
            "current_full_metrics": data_dir / "CityScore_Full_Metric_list.xlsx",
            "current_summary": data_dir / "CityScore_Summary.xlsx",
            "historical_city_agg": data_dir / "rpt_city_score_agg_v.csv.xlsx",
            "historical_metric_summary": data_dir / "rpt_city_score_summary.csv.xlsx",
        }

        object.__setattr__(self, "repo_root", repo_root)
        object.__setattr__(self, "data_dir", data_dir)
        object.__setattr__(self, "cleaned_dir", cleaned_dir)
        object.__setattr__(self, "aggregated_dir", aggregated_dir)
        object.__setattr__(self, "persist_outputs_default", not self.is_vercel)
        object.__setattr__(self, "raw_files", raw_files)

    def ensure_directories(self) -> None:
        self.cleaned_dir.mkdir(parents=True, exist_ok=True)
        self.aggregated_dir.mkdir(parents=True, exist_ok=True)

    def validate_input_files(self) -> None:
        missing_files = [str(path) for path in self.raw_files.values() if not path.exists()]
        if missing_files:
            raise FileNotFoundError(
                "Missing required source files. "
                f"Expected them under '{self.data_dir}'. Missing: {missing_files}. "
                "If Vercel Base Directory is 'Codes', commit the workbook files under 'Codes/Excel/' "
                "or set CITYSCORE_DATA_DIR to a readable directory bundled with the deployment."
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
