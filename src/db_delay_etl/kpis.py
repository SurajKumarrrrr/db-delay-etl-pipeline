"""KPI queries on the loaded star schema."""

from __future__ import annotations

import duckdb
import pandas as pd

# Punctuality follows the DB definition: share of stops that actually ran with < 6 min delay.
OVERALL = """
SELECT count(*)                                         AS stops,
       round(100 * avg(is_punctual::INT) FILTER (WHERE NOT is_cancelled), 1)            AS punctuality_pct,
       round(100 * avg(is_cancelled::INT), 2)           AS cancellation_pct,
       round(avg(delay_min) FILTER (WHERE delay_min > 0), 1) AS avg_delay_when_late_min
FROM fact_stop_event
"""

BY_CATEGORY = """
SELECT category,
       count(*)                                AS stops,
       round(100 * avg(is_punctual::INT) FILTER (WHERE NOT is_cancelled), 1)   AS punctuality_pct,
       round(quantile_cont(delay_min, 0.95), 0) AS p95_delay_min
FROM fact_stop_event
GROUP BY category
ORDER BY punctuality_pct
"""

WORST_STATIONS = """
SELECT s.station_name,
       count(*)                                AS stops,
       round(100 * avg(f.is_punctual::INT) FILTER (WHERE NOT f.is_cancelled), 1) AS punctuality_pct,
       round(avg(f.delay_min), 1)              AS avg_delay_min
FROM fact_stop_event f
JOIN dim_station s USING (eva_id)
GROUP BY s.station_name
ORDER BY punctuality_pct
LIMIT ?
"""

BY_HOUR = """
SELECT planned_hour,
       count(*)                                AS stops,
       round(100 * avg(is_punctual::INT) FILTER (WHERE NOT is_cancelled), 1)   AS punctuality_pct
FROM fact_stop_event
GROUP BY planned_hour
ORDER BY planned_hour
"""

WEEKDAY_VS_WEEKEND = """
SELECT CASE WHEN dayofweek(service_day) IN (0, 6) THEN 'weekend' ELSE 'weekday' END AS day_type,
       count(*)                                AS stops,
       round(100 * avg(is_punctual::INT) FILTER (WHERE NOT is_cancelled), 1)   AS punctuality_pct
FROM fact_stop_event
GROUP BY day_type
ORDER BY day_type
"""


def overall(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return con.execute(OVERALL).df()


def by_category(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return con.execute(BY_CATEGORY).df()


def worst_stations(con: duckdb.DuckDBPyConnection, n: int = 5) -> pd.DataFrame:
    return con.execute(WORST_STATIONS, [n]).df()


def by_hour(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return con.execute(BY_HOUR).df()


def weekday_vs_weekend(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return con.execute(WEEKDAY_VS_WEEKEND).df()
