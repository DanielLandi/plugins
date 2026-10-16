import pytest

import lv
from lv import version


@pytest.mark.parametrize("s, want", [
    ("1.0.0", (1, 0, 0)), ("12.34.5678", (12, 34, 5678)),
    ("1.0", None), ("1.0.0-beta", None), ("v1.0.0", None), ("", None), (None, None),
    ("12345.0.0", None), (" 1.0.0", None), ("<script>", None), (1, None),
])
def test_parse(s, want):
    assert version.parse(s) == want


def test_update_line_only_for_a_newer_version_with_the_same_major(monkeypatch):
    monkeypatch.setattr(lv, "__version__", "1.2.3")
    line = version.update_line("1.3.0")
    assert line == ("A newer lesson-videos (1.3.0) is available. To update: run /plugin update lesson-videos, "
                    "then close and reopen Claude Code, then run /lesson-videos:serve.")
    assert version.update_line("1.2.4").startswith("A newer lesson-videos (1.2.4)")
    for latest in ("1.2.3", "1.2.2", "1.0.0", "2.0.0", "0.9.0", "junk", None):
        assert version.update_line(latest) is None, latest


def test_moved_notice_gives_the_three_steps():
    m = version.MOVED
    assert m.startswith("lesson-videos is now slide2video.")
    for step in ("/plugin marketplace add slide2video/slide2video-plugin", "/plugin install slide2video@slide2video",
                 "/plugin uninstall lesson-videos", "close and reopen Claude Code"):
        assert step in m


def test_worker_status_prints_the_moved_notice(monkeypatch, capsys):
    from lv import cli, site
    monkeypatch.setattr(site, "status", lambda: {"teacher_email": "t@example.com", "device_name": "Mac"})
    assert cli.main(["worker", "--status"]) == 0
    assert version.MOVED in capsys.readouterr().out
