from datetime import date
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
STATIONS = ROOT / "data" / "reference" / "stations.csv"


@pytest.fixture
def stations_path() -> Path:
    return STATIONS


@pytest.fixture
def raw_rows() -> pd.DataFrame:
    """Hand-written raw rows covering every cleaning rule."""
    rows = [
        # punctual ICE, 3 min late
        ("ICE-1-261001", "8000105", "Frankfurt (Main) Hbf", "ICE", "2610010800", "2610010803", ""),
        # exact duplicate of the row above (overlapping poll)
        ("ICE-1-261001", "8000105", "Frankfurt (Main) Hbf", "ICE", "2610010800", "2610010803", ""),
        # late RE, 12 min, messy casing / whitespace
        ("RE-2-261001", "8000207", "  KÖLN HBF ", " re", "2610011700", "2610011712", ""),
        # cancelled IC, no actual time
        ("IC-3-261001", "8000115", "Fulda", "IC", "2610010900", "", "c"),
        # missing actual but not cancelled -> dropped
        ("S-4-261001", "8000105", "Frankfurt (Main) Hbf", "S", "2610011000", "", ""),
        # unknown category -> dropped
        ("BUS-5-261001", "8000105", "Frankfurt (Main) Hbf", "BUS", "2610011100", "2610011100", ""),
        # implausible: 20 minutes early -> dropped
        ("S-6-261001", "8000105", "Frankfurt (Main) Hbf", "S", "2610011200", "2610011140", ""),
        # unparseable planned timestamp -> dropped
        ("S-7-261001", "8000105", "Frankfurt (Main) Hbf", "S", "not-a-time", "2610011200", ""),
        # exactly 6 min late -> NOT punctual (threshold is < 6)
        ("ICE-8-261001", "8000261", "München Hbf", "ICE", "2610011300", "2610011306", ""),
        # same trip/station/planned as ICE-8 but corrected later -> keep latest actual
        ("ICE-8-261001", "8000261", "München Hbf", "ICE", "2610011300", "2610011308", ""),
    ]
    cols = ["trip_id", "eva_id", "station_name", "category", "planned_arrival", "actual_arrival", "cancelled"]
    df = pd.DataFrame(rows, columns=cols)
    df["service_day"] = date(2026, 10, 1).isoformat()
    return df
