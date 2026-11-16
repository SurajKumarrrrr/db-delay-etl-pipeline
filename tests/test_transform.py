from db_delay_etl.transform import clean


def test_report_counts_every_rule(raw_rows):
    facts, rep = clean(raw_rows)
    assert rep.input_rows == 10
    assert rep.duplicates_removed == 1
    assert rep.invalid_category == 1
    assert rep.unparseable_planned == 1
    assert rep.missing_actual_not_cancelled == 1
    assert rep.implausible_delay == 1
    assert rep.output_rows == len(facts) == 4


def test_delay_and_punctuality(raw_rows):
    facts, _ = clean(raw_rows)
    by_trip = facts.set_index("trip_id")
    assert by_trip.loc["ICE-1-261001", "delay_min"] == 3
    assert bool(by_trip.loc["ICE-1-261001", "is_punctual"])
    assert by_trip.loc["RE-2-261001", "delay_min"] == 12
    assert not bool(by_trip.loc["RE-2-261001", "is_punctual"])


def test_six_minutes_is_not_punctual_and_latest_poll_wins(raw_rows):
    facts, _ = clean(raw_rows)
    row = facts[facts["trip_id"] == "ICE-8-261001"]
    assert len(row) == 1
    assert row["delay_min"].iloc[0] == 8
    assert not bool(row["is_punctual"].iloc[0])


def test_cancellation_kept_without_delay(raw_rows):
    facts, _ = clean(raw_rows)
    row = facts[facts["trip_id"] == "IC-3-261001"].iloc[0]
    assert bool(row["is_cancelled"])
    assert not bool(row["is_punctual"])
    assert row["delay_min"] is None or str(row["delay_min"]) == "<NA>"


def test_categories_normalised(raw_rows):
    facts, _ = clean(raw_rows)
    assert set(facts["category"]) <= {"ICE", "IC", "RE", "S"}
