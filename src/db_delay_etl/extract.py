"""Extract step: read raw daily files as strings, exactly as delivered."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pandas as pd

RAW_COLUMNS = [
    "trip_id",
    "eva_id",
    "station_name",
    "category",
    "planned_arrival",
    "actual_arrival",
    "cancelled",
]
_FILE_RE = re.compile(r"stop_events_(\d{4}-\d{2}-\d{2})\.csv$")


def service_day(path: Path) -> date:
    """Parse the service day from a raw file name."""
    m = _FILE_RE.search(path.name)
    if not m:
        raise ValueError(f"Unexpected raw file name: {path.name}")
    return date.fromisoformat(m.group(1))


def list_raw_files(raw_dir: Path, start: date | None = None, end: date | None = None) -> list[Path]:
    """Raw files in ``raw_dir`` whose service day is within [start, end]."""
    files = []
    for p in sorted(raw_dir.glob("stop_events_*.csv")):
        d = service_day(p)
        if (start is None or d >= start) and (end is None or d <= end):
            files.append(p)
    return files


def read_raw(path: Path) -> pd.DataFrame:
    """Read a raw file with every column as string, validating the header."""
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    missing = set(RAW_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"{path.name} is missing columns: {sorted(missing)}")
    df = df[RAW_COLUMNS].copy()
    df["service_day"] = service_day(path).isoformat()
    return df
