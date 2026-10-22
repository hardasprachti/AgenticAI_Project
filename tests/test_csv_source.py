from datetime import date

import pytest

from pulse.sources.csv_source import CsvSource, CsvSourceError

HEADER = "review_id,date,rating,title,text,author_name,author_id,app_version\n"


def _write(tmp_path, body: str, header: str = HEADER):
    path = tmp_path / "reviews.csv"
    path.write_text(header + body, encoding="utf-8")
    return path


def test_reads_all_fields(tmp_path):
    path = _write(tmp_path, "a1,2026-09-01,2,Slow,App is slow,Asha K,u-9,5.1\n")
    [review] = CsvSource(path).fetch(date(2026, 8, 1), date(2026, 9, 30))
    assert (review.store, review.store_review_id, review.rating) == ("play", "a1", 2)
    assert (review.title, review.text, review.app_version) == ("Slow", "App is slow", "5.1")
    assert (review.author_name, review.author_id) == ("Asha K", "u-9")


def test_window_is_inclusive_on_both_ends(tmp_path):
    dates = ["2026-08-31", "2026-09-01", "2026-09-30", "2026-10-01"]
    body = "".join(f"{rid},{day},3,t,x,,,\n" for rid, day in zip("abcd", dates, strict=True))
    got = CsvSource(_write(tmp_path, body)).fetch(date(2026, 9, 1), date(2026, 9, 30))
    assert [r.store_review_id for r in got] == ["b", "c"]


def test_bad_rows_are_counted_not_fatal(tmp_path):
    body = "a,2026-09-01,x,t,text,,,\nb,not-a-date,3,t,text,,,\nc,2026-09-02,4,t,text,,,\n"
    source = CsvSource(_write(tmp_path, body))
    got = source.fetch(date(2026, 8, 1), date(2026, 9, 30))
    assert [r.store_review_id for r in got] == ["c"]
    assert (source.rows_read, source.rows_skipped) == (3, 2)


def test_play_console_export_headers(tmp_path):
    header = (
        "Package Name,App Version Name,Star Rating,Review Title,Review Text,"
        "Review Submit Date and Time\n"
    )
    body = "com.nextbillion.groww,9.9,1,Bad,Does not open,2026-09-05T10:20:30Z\n"
    [review] = CsvSource(_write(tmp_path, body, header)).fetch(date(2026, 9, 1), date(2026, 9, 30))
    assert (review.rating, review.date, review.app_version) == (1, date(2026, 9, 5), "9.9")
    assert review.store_review_id == "row-1"
    assert review.author_name is None


def test_missing_required_column_rejected(tmp_path):
    path = _write(tmp_path, "x\n", header="foo\n")
    with pytest.raises(CsvSourceError, match="missing required"):
        CsvSource(path).fetch(date(2026, 1, 1), date(2026, 12, 31))


def test_missing_file_rejected(tmp_path):
    with pytest.raises(CsvSourceError, match="not found"):
        CsvSource(tmp_path / "nope.csv").fetch(date(2026, 1, 1), date(2026, 12, 31))
