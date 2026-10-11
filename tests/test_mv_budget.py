from datetime import date, datetime, timedelta, timezone

import pytest

from mv_fixtures import valid_spec
from musicvideo.budget import cycle_start, downloads_in_cycle
from musicvideo.cli import main
from musicvideo.spec import load_spec, save_spec

ID = "night-drive"


@pytest.mark.parametrize("today, day, expected", [
    (date(2026, 10, 20), 15, date(2026, 10, 15)),
    (date(2026, 10, 15), 15, date(2026, 10, 15)),
    (date(2026, 10, 2), 15, date(2026, 9, 15)),
    (date(2026, 1, 10), 15, date(2025, 12, 15)),
    (date(2026, 2, 28), 31, date(2026, 2, 28)),
    (date(2026, 3, 5), 31, date(2026, 2, 28)),
    (date(2028, 2, 29), 30, date(2028, 2, 29)),
])
def test_cycle_start(today, day, expected):
    assert cycle_start(today, day) == expected


def _spec(at):
    return {"kept": {"downloaded_at": at}} if at else {"status": "drafted"}


def test_counts_only_current_cycle():
    specs = [_spec("2026-10-16T10:00:00-03:00"), _spec("2026-10-14T10:00:00-03:00"), _spec(None)]
    assert downloads_in_cycle(specs, date(2026, 10, 20), 15) == 1


def test_accepts_datetime_values_from_unquoted_yaml():
    specs = [_spec(datetime(2026, 10, 16, 13, 0, tzinfo=timezone.utc))]
    assert downloads_in_cycle(specs, date(2026, 10, 20), 15) == 1


def _iso(delta=timedelta()):
    return (datetime.now().astimezone() + delta).isoformat(timespec="seconds")


def test_round_appends_and_marks_generated(write_spec, capsys):
    path = write_spec()
    assert main(["round", ID, "--changes", "initial",
                 "--url", "https://suno.com/song/a", "--url", "https://suno.com/song/b"]) == 0
    data = load_spec(path)
    assert data["status"] == "generated"
    assert data["rounds"][0]["suno_urls"] == ["https://suno.com/song/a", "https://suno.com/song/b"]
    assert "round 1 recorded" in capsys.readouterr().out


def test_rejected_round_keeps_drafted(write_spec):
    path = write_spec()
    assert main(["round", ID, "--changes", "rejected: too close to an existing song"]) == 0
    data = load_spec(path)
    assert data["status"] == "drafted"
    assert data["rounds"][0]["suno_urls"] == []


def test_downloaded_records_and_reports_count(write_spec, capsys):
    path = write_spec(status="generated")
    assert main(["downloaded", ID, "--take-url", "https://suno.com/song/a"]) == 0
    data = load_spec(path)
    assert data["status"] == "downloaded"
    assert data["kept"]["take_url"] == "https://suno.com/song/a"
    assert "download 1 of 20" in capsys.readouterr().out


def test_downloaded_refuses_twice(write_spec, capsys):
    write_spec(status="downloaded", kept={"take_url": "u", "downloaded_at": _iso()})
    assert main(["downloaded", ID, "--take-url", "u"]) == 2
    assert "already downloaded" in capsys.readouterr().err


def test_downloaded_refuses_when_budget_used(mv_ws, write_spec, capsys):
    for i in range(20):
        data = valid_spec(id=f"song-{i}", status="downloaded", kept={"take_url": "u", "downloaded_at": _iso()})
        save_spec(mv_ws.specs_dir / f"song-{i}.yaml", data)
    write_spec(status="generated")
    assert main(["downloaded", ID, "--take-url", "u"]) == 2
    err = capsys.readouterr().err
    assert "budget used up: 20 of 20" in err and "the user confirmed" in err
    assert main(["downloaded", ID, "--take-url", "u", "--paid-extra"]) == 0
    assert "download 21 of 20" in capsys.readouterr().out


def test_downloaded_undo(write_spec):
    path = write_spec(status="downloaded", kept={"take_url": "u", "downloaded_at": _iso()})
    assert main(["downloaded", ID, "--undo"]) == 0
    data = load_spec(path)
    assert data["status"] == "generated"
    assert "kept" not in data


def test_status_summary(write_spec, capsys):
    write_spec(status="downloaded", kept={"take_url": "u", "downloaded_at": _iso()})
    assert main(["status"]) == 0
    out = capsys.readouterr().out
    assert "1 of 20 used" in out
    assert "drafted 0 · generated 0 · downloaded 1 · filed 0" in out


def test_downloaded_needs_budget_settings(mv_ws, capsys):
    cfg = mv_ws.home / "config.yaml"
    cfg.write_text(cfg.read_text(encoding="utf-8").replace("billing_day: 15", "billing_day: null"), encoding="utf-8")
    save_spec(mv_ws.specs_dir / f"{ID}.yaml", valid_spec(status="generated"))
    assert main(["downloaded", ID, "--take-url", "https://suno.com/song/x"]) == 2
    err = capsys.readouterr().err
    assert "billing_day" in err and "config.yaml" in err and "Suno account" in err


def test_status_without_budget_settings(mv_ws, capsys):
    cfg = mv_ws.home / "config.yaml"
    cfg.write_text(cfg.read_text(encoding="utf-8").replace("download_budget: 20", "download_budget: null"), encoding="utf-8")
    assert main(["status"]) == 0
    assert "not tracked" in capsys.readouterr().out
