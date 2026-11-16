"""Deterministic generator for raw, realistically messy stop-event files.

The output mimics what you get when you poll a timetable API every day:
one CSV per service day, timestamps in the compact ``yyMMddHHmm`` format,
duplicated rows from overlapping polls, missing actual times, cancellations
and inconsistent whitespace/casing in free-text columns.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

TS_FORMAT = "%y%m%d%H%M"

# category -> (share of traffic, mean delay in minutes when late, cancellation rate)
CATEGORIES = {
    "ICE": (0.30, 9.0, 0.025),
    "IC": (0.15, 8.0, 0.020),
    "RE": (0.30, 4.0, 0.015),
    "S": (0.25, 3.0, 0.010),
}


def _hour_weights() -> np.ndarray:
    """Departures per hour: quiet nights, morning and evening peaks."""
    w = np.array([1, 0.5, 0.3, 0.3, 1, 3, 7, 10, 9, 6, 5, 5, 5, 5, 6, 8, 10, 10, 8, 6, 4, 3, 2, 1.5])
    return w / w.sum()


def _rush_multiplier(hour: int) -> float:
    return 1.6 if hour in (7, 8, 16, 17, 18) else 1.0


def generate_day(day: date, stations: pd.DataFrame, n_events: int, rng: np.random.Generator) -> pd.DataFrame:
    """Generate raw stop events for one service day."""
    cats = list(CATEGORIES)
    cat_p = np.array([CATEGORIES[c][0] for c in cats])
    category = rng.choice(cats, size=n_events, p=cat_p / cat_p.sum())
    station_idx = rng.integers(0, len(stations), size=n_events)
    hours = rng.choice(24, size=n_events, p=_hour_weights())
    minutes = rng.integers(0, 60, size=n_events)

    weekend = day.weekday() >= 5
    rows = []
    for i in range(n_events):
        st = stations.iloc[station_idx[i]]
        cat = category[i]
        _, mean_delay, cancel_rate = CATEGORIES[cat]
        planned = datetime.combine(day, datetime.min.time()) + timedelta(hours=int(hours[i]), minutes=int(minutes[i]))

        factor = st["delay_factor"] * _rush_multiplier(int(hours[i])) * (0.8 if weekend else 1.0)
        cancelled = rng.random() < cancel_rate * factor
        if rng.random() < 0.30 * factor:  # late
            delay = int(rng.exponential(mean_delay * factor)) + 1
        else:  # on time or slightly early
            delay = int(rng.choice([-1, 0, 0, 0, 1]))
        actual = None if cancelled else planned + timedelta(minutes=delay)

        rows.append(
            {
                "trip_id": f"{cat}-{rng.integers(100, 9999)}-{day:%y%m%d}",
                "eva_id": int(st["eva_id"]),
                # free text from the source is messy on purpose
                "station_name": st["station_name"] if rng.random() > 0.05 else f"  {st['station_name'].upper()} ",
                "category": cat if rng.random() > 0.03 else cat.lower(),
                "planned_arrival": planned.strftime(TS_FORMAT),
                "actual_arrival": "" if actual is None or rng.random() < 0.01 else actual.strftime(TS_FORMAT),
                "cancelled": "c" if cancelled else "",
            }
        )

    df = pd.DataFrame(rows)
    # overlapping API polls produce exact duplicates
    dupes = df.sample(frac=0.04, random_state=int(rng.integers(0, 2**31 - 1)))
    return pd.concat([df, dupes], ignore_index=True)


def generate(
    out_dir: Path,
    stations_path: Path,
    start: date,
    days: int,
    events_per_day: int = 2000,
    seed: int = 42,
) -> list[Path]:
    """Write one raw CSV per day to ``out_dir`` and return the paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    stations = pd.read_csv(stations_path)
    rng = np.random.default_rng(seed)
    paths = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        df = generate_day(day, stations, events_per_day, rng)
        path = out_dir / f"stop_events_{day:%Y-%m-%d}.csv"
        df.to_csv(path, index=False)
        paths.append(path)
    return paths
