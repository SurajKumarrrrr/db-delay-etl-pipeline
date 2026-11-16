"""Command-line entry point: generate raw data, run the ETL, print a KPI report."""

from __future__ import annotations

import argparse
import logging
from datetime import date
from pathlib import Path

import pandas as pd

from . import kpis
from .extract import list_raw_files, read_raw, service_day
from .generate import generate
from .load import connect, load_day, load_stations
from .transform import clean

log = logging.getLogger("db_delay_etl")

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RAW = ROOT / "data" / "raw"
DEFAULT_DB = ROOT / "data" / "warehouse.duckdb"
DEFAULT_STATIONS = ROOT / "data" / "reference" / "stations.csv"


def run_etl(
    raw_dir: Path,
    db_path: Path,
    stations_path: Path,
    start: date | None = None,
    end: date | None = None,
) -> dict[str, dict[str, int]]:
    """Run extract -> transform -> load for every raw file in the date range."""
    con = connect(db_path)
    load_stations(con, pd.read_csv(stations_path))
    reports = {}
    files = list_raw_files(raw_dir, start, end)
    if not files:
        log.warning("No raw files found in %s", raw_dir)
    for path in files:
        day = service_day(path).isoformat()
        raw = read_raw(path)
        facts, rep = clean(raw)
        load_day(con, facts, day, rep.input_rows)
        reports[day] = rep.as_dict()
        log.info("%s: %d raw -> %d clean rows %s", day, rep.input_rows, rep.output_rows, rep.as_dict())
    con.close()
    return reports


def print_report(db_path: Path) -> None:
    con = connect(db_path)
    pd.set_option("display.width", 120)
    sections = [
        ("Overall", kpis.overall(con)),
        ("By train category", kpis.by_category(con)),
        ("Least punctual stations", kpis.worst_stations(con)),
        ("Weekday vs weekend", kpis.weekday_vs_weekend(con)),
        ("By planned hour", kpis.by_hour(con)),
    ]
    for title, df in sections:
        print(f"\n## {title}\n")
        print(df.to_string(index=False))
    con.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="db-delay-etl", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="write synthetic raw daily files")
    g.add_argument("--start", type=date.fromisoformat, default=date(2026, 10, 1))
    g.add_argument("--days", type=int, default=30)
    g.add_argument("--events-per-day", type=int, default=2000)
    g.add_argument("--seed", type=int, default=42)
    g.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW)

    r = sub.add_parser("run", help="run the ETL for raw files in a date range")
    r.add_argument("--start", type=date.fromisoformat)
    r.add_argument("--end", type=date.fromisoformat)
    r.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW)
    r.add_argument("--db", type=Path, default=DEFAULT_DB)

    rep = sub.add_parser("report", help="print KPI report from the warehouse")
    rep.add_argument("--db", type=Path, default=DEFAULT_DB)

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if args.cmd == "generate":
        paths = generate(args.raw_dir, DEFAULT_STATIONS, args.start, args.days, args.events_per_day, args.seed)
        log.info("Wrote %d raw files to %s", len(paths), args.raw_dir)
    elif args.cmd == "run":
        run_etl(args.raw_dir, args.db, DEFAULT_STATIONS, args.start, args.end)
    elif args.cmd == "report":
        print_report(args.db)


if __name__ == "__main__":
    main()
