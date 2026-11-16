"""Transform step: clean raw stop events into an analysis-ready fact table."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

TS_FORMAT = "%y%m%d%H%M"
# Deutsche Bahn counts a stop as punctual if the delay is below 6 minutes.
PUNCTUALITY_THRESHOLD_MIN = 6
VALID_CATEGORIES = {"ICE", "IC", "RE", "S"}
MAX_PLAUSIBLE_DELAY_MIN = 600
MAX_EARLY_MIN = 5


@dataclass
class TransformReport:
    """Row counts for every cleaning rule, so data loss is never silent."""

    input_rows: int = 0
    duplicates_removed: int = 0
    invalid_category: int = 0
    unparseable_planned: int = 0
    implausible_delay: int = 0
    missing_actual_not_cancelled: int = 0
    output_rows: int = 0
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, int]:
        return {k: v for k, v in self.__dict__.items() if k != "notes"}


def clean(raw: pd.DataFrame) -> tuple[pd.DataFrame, TransformReport]:
    """Clean raw events. Returns the fact rows and a report of what was dropped."""
    rep = TransformReport(input_rows=len(raw))
    df = raw.copy()

    before = len(df)
    df = df.drop_duplicates()
    rep.duplicates_removed = before - len(df)

    df["category"] = df["category"].str.strip().str.upper()
    bad_cat = ~df["category"].isin(VALID_CATEGORIES)
    rep.invalid_category = int(bad_cat.sum())
    df = df[~bad_cat]

    df["station_name"] = df["station_name"].str.strip()
    df["eva_id"] = pd.to_numeric(df["eva_id"], errors="coerce").astype("Int64")

    df["planned_arrival"] = pd.to_datetime(df["planned_arrival"], format=TS_FORMAT, errors="coerce")
    df["actual_arrival"] = pd.to_datetime(df["actual_arrival"].replace("", None), format=TS_FORMAT, errors="coerce")
    bad_planned = df["planned_arrival"].isna() | df["eva_id"].isna()
    rep.unparseable_planned = int(bad_planned.sum())
    df = df[~bad_planned]

    df["is_cancelled"] = df["cancelled"].str.strip().str.lower().eq("c")

    # A stop that is neither cancelled nor has an actual time cannot be scored.
    no_actual = df["actual_arrival"].isna() & ~df["is_cancelled"]
    rep.missing_actual_not_cancelled = int(no_actual.sum())
    df = df[~no_actual]

    delay = (df["actual_arrival"] - df["planned_arrival"]).dt.total_seconds() / 60
    df["delay_min"] = delay.round().astype("Int64")
    implausible = df["delay_min"].notna() & (
        (df["delay_min"] > MAX_PLAUSIBLE_DELAY_MIN) | (df["delay_min"] < -MAX_EARLY_MIN)
    )
    rep.implausible_delay = int(implausible.sum())
    df = df[~implausible]

    df["is_punctual"] = (~df["is_cancelled"]) & (df["delay_min"] < PUNCTUALITY_THRESHOLD_MIN)
    df["planned_hour"] = df["planned_arrival"].dt.hour

    # Same trip at same station and planned time can still appear twice with
    # different actuals (a later poll corrected it): keep the latest actual.
    df = df.sort_values("actual_arrival").drop_duplicates(
        subset=["trip_id", "eva_id", "planned_arrival"], keep="last"
    )

    out = df[
        [
            "service_day",
            "trip_id",
            "eva_id",
            "category",
            "planned_arrival",
            "actual_arrival",
            "planned_hour",
            "delay_min",
            "is_cancelled",
            "is_punctual",
        ]
    ].reset_index(drop=True)
    out["is_punctual"] = out["is_punctual"].fillna(False).astype(bool)
    rep.output_rows = len(out)
    return out, rep
