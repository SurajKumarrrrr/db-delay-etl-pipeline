"""Load step: idempotent loads into a small DuckDB star schema."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

DDL = """
CREATE TABLE IF NOT EXISTS dim_station (
    eva_id       BIGINT PRIMARY KEY,
    station_name VARCHAR NOT NULL,
    state        VARCHAR NOT NULL
);
CREATE TABLE IF NOT EXISTS fact_stop_event (
    service_day     DATE      NOT NULL,
    trip_id         VARCHAR   NOT NULL,
    eva_id          BIGINT    NOT NULL,
    category        VARCHAR   NOT NULL,
    planned_arrival TIMESTAMP NOT NULL,
    actual_arrival  TIMESTAMP,
    planned_hour    TINYINT   NOT NULL,
    delay_min       INTEGER,
    is_cancelled    BOOLEAN   NOT NULL,
    is_punctual     BOOLEAN   NOT NULL,
    PRIMARY KEY (trip_id, eva_id, planned_arrival)
);
CREATE TABLE IF NOT EXISTS etl_run_log (
    loaded_at   TIMESTAMP DEFAULT current_timestamp,
    service_day DATE,
    input_rows  INTEGER,
    output_rows INTEGER
);
"""


def connect(db_path: Path | str) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(db_path))
    con.execute(DDL)
    return con


def load_stations(con: duckdb.DuckDBPyConnection, stations: pd.DataFrame) -> None:
    """Replace the station dimension from the reference file."""
    con.register("stations_df", stations[["eva_id", "station_name", "state"]])
    con.execute("DELETE FROM dim_station")
    con.execute("INSERT INTO dim_station SELECT * FROM stations_df")
    con.unregister("stations_df")


def load_day(con: duckdb.DuckDBPyConnection, facts: pd.DataFrame, service_day: str, input_rows: int) -> int:
    """Replace one service day's partition (delete + insert in one transaction).

    Re-running the pipeline for a day therefore never creates duplicates.
    """
    con.register("facts_df", facts)
    con.execute("BEGIN TRANSACTION")
    try:
        con.execute("DELETE FROM fact_stop_event WHERE service_day = ?", [service_day])
        con.execute(
            """
            INSERT INTO fact_stop_event
            SELECT CAST(service_day AS DATE), trip_id, eva_id, category, planned_arrival,
                   actual_arrival, planned_hour, delay_min, is_cancelled, is_punctual
            FROM facts_df
            """
        )
        con.execute(
            "INSERT INTO etl_run_log (service_day, input_rows, output_rows) VALUES (?, ?, ?)",
            [service_day, input_rows, len(facts)],
        )
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.unregister("facts_df")
    return len(facts)
