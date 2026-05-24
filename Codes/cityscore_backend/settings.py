from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    project_root: Path = field(default_factory=lambda: Path(__file__).resolve().parents[2])
    rolling_windows: tuple[int, int] = (14, 28)
    top_alert_limit: int = 5
    stale_metric_threshold_days: int = 3

    data_dir: Path = field(init=False)
    cleaned_dir: Path = field(init=False)
    aggregated_dir: Path = field(init=False)
    raw_files: dict[str, Path] = field(init=False)

    def __post_init__(self) -> None:
        data_dir = self.project_root / "Excel"
        cleaned_dir = self.project_root / "cleaned csv"
        aggregated_dir = self.project_root / "aggregated data"
        raw_files = {
            "current_full_metrics": data_dir / "CityScore_Full_Metric_list.xlsx",
            "current_summary": data_dir / "CityScore_Summary.xlsx",
            "historical_city_agg": data_dir / "rpt_city_score_agg_v.csv.xlsx",
            "historical_metric_summary": data_dir / "rpt_city_score_summary.csv.xlsx",
        }

        object.__setattr__(self, "data_dir", data_dir)
        object.__setattr__(self, "cleaned_dir", cleaned_dir)
        object.__setattr__(self, "aggregated_dir", aggregated_dir)
        object.__setattr__(self, "raw_files", raw_files)

    def ensure_directories(self) -> None:
        self.cleaned_dir.mkdir(parents=True, exist_ok=True)
        self.aggregated_dir.mkdir(parents=True, exist_ok=True)

    def validate_input_files(self) -> None:
        missing_files = [str(path) for path in self.raw_files.values() if not path.exists()]
        if missing_files:
            raise FileNotFoundError(f"Missing required source files: {missing_files}")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings

