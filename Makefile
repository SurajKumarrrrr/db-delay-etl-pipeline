.PHONY: install test lint run clean

install:
	pip install -r requirements.txt
	pip install -e .

test:
	pytest -q

lint:
	ruff check .

run:
	python -m db_delay_etl.pipeline generate --days 30
	python -m db_delay_etl.pipeline run
	python -m db_delay_etl.pipeline report

clean:
	rm -rf data/raw data/warehouse.duckdb
