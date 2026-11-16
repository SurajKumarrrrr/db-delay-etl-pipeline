from datetime import date

import pandas as pd
import pytest

from db_delay_etl import kpis
from db_delay_etl.extract import list_raw_files, read_raw, service_day
from db_delay_etl.generate import generate
from db_delay_etl.load import connect
from db_delay_etl.pipeline import run_etl


@pytest.fixture
def raw_dir(tmp_path, stations_path):
    out = tmp_path / "raw"
    generate(out, stations_path, date(2026, 10, 1), days=3, events_per_day=300, seed=7)
    return out


def test_generator_is_deterministic(tmp_path, stations_path):
    a = generate(tmp_path / "a", stations_path, date(2026, 10, 1), 1, 200, seed=1)[0]
    b = generate(tmp_path / "b", stations_path, date(2026, 10, 1), 1, 200, seed=1)[0]
    pd.testing.assert_frame_equal(pd.read_csv(a), pd.read_csv(b))


def test_extract_filters_by_date(raw_dir):
    files = list_raw_files(raw_dir, start=date(2026, 10, 2), end=date(2026, 10, 2))
    assert [service_day(f) for f in files] == [date(2026, 10, 2)]
    assert read_raw(files[0])["service_day"].unique().tolist() == ["2026-10-02"]


def test_bad_file_name_rejected(tmp_path):
    with pytest.raises(ValueError):
        service_day(tmp_path / "events.csv")


def test_etl_is_idempotent(raw_dir, tmp_path, stations_path):
    db = tmp_path / "wh.duckdb"
    run_etl(raw_dir, db, stations_path)
    con = connect(db)
    first = con.execute("SELECT count(*) FROM fact_stop_event").fetchone()[0]
    con.close()

    run_etl(raw_dir, db, stations_path)  # re-run the same days
    con = connect(db)
    second = con.execute("SELECT count(*) FROM fact_stop_event").fetchone()[0]
    dupes = con.execute(
        "SELECT count(*) FROM (SELECT trip_id, eva_id, planned_arrival FROM fact_stop_event "
        "GROUP BY ALL HAVING count(*) > 1)"
    ).fetchone()[0]
    con.close()
    assert first == second > 0
    assert dupes == 0


def test_every_fact_has_a_station(raw_dir, tmp_path, stations_path):
    db = tmp_path / "wh.duckdb"
    run_etl(raw_dir, db, stations_path)
    con = connect(db)
    orphans = con.execute(
        "SELECT count(*) FROM fact_stop_event f LEFT JOIN dim_station s USING (eva_id) WHERE s.eva_id IS NULL"
    ).fetchone()[0]
    assert orphans == 0
    con.close()


def test_kpis_are_sane(raw_dir, tmp_path, stations_path):
    db = tmp_path / "wh.duckdb"
    run_etl(raw_dir, db, stations_path)
    con = connect(db)
    o = kpis.overall(con).iloc[0]
    assert 0 < o["punctuality_pct"] <= 100
    assert 0 <= o["cancellation_pct"] < 20
    assert len(kpis.by_hour(con)) <= 24
    assert set(kpis.by_category(con)["category"]) <= {"ICE", "IC", "RE", "S"}
    assert len(kpis.worst_stations(con, n=3)) == 3
    con.close()
