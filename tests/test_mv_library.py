import http.client
import plistlib
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from musicvideo import library
from musicvideo.cli import main

# Starting the library at login goes through launchd (`launchctl ... gui/<uid>`); Windows has no os.getuid.
macos_only = pytest.mark.skipif(sys.platform != "darwin", reason="the login item is a macOS launchd agent")


@pytest.fixture
def results(tmp_path):
    """A results folder shaped like the plugins write it, with tiny stand-in files."""
    root = tmp_path / "Results é"
    video = root / "night-drive"
    video.mkdir(parents=True)
    (video / "README.md").write_text("# Night Drive (night-drive)\n\nMade with the plugin.\n", encoding="utf-8")
    (video / "Night Drive.mp4").write_bytes(bytes(range(256)) * 40)
    (video / "Night Drive (vertical).mp4").write_bytes(b"v" * 100)
    (video / "Night Drive.vtt").write_text("WEBVTT\n", encoding="utf-8")
    (video / "thumbnail.png").write_bytes(b"png")
    (video / "Night Drive.mp3").write_bytes(b"copy")
    (video / "Artist - Night Drive.mp3").write_bytes(b"filed")
    (video / "Night Drive.wav").write_bytes(b"master")
    (video / "web" / "assets").mkdir(parents=True)
    (video / "web" / "index.html").write_text("<html></html>", encoding="utf-8")
    (video / "web" / "assets" / "app.js").write_text("1", encoding="utf-8")
    (video / "notes.js").write_text("1", encoding="utf-8")
    (video / "_source").mkdir()
    (video / "_source" / "take.mp4").write_bytes(b"paid")
    unit = root / "lessons" / "course-a" / "unit-1"
    unit.mkdir(parents=True)
    for name in ("Chapter 10 - Last.mp4", "Chapter 2 - Second.mp4"):
        (unit / name).write_bytes(b"x")
    (root / ".plexignore").write_text("*", encoding="utf-8")
    return root


def test_scan_lists_projects_and_skips_working_files(results):
    shelves = {s.rel: s for s in library.scan(results)}
    assert set(shelves) == {"night-drive", "lessons/course-a/unit-1"}
    night = shelves["night-drive"]
    assert night.title == "Night Drive"
    assert [v.title for v in night.videos] == ["Night Drive", "Night Drive (vertical)"]
    assert night.videos[0].art == "night-drive/thumbnail.png" and night.videos[0].subs == "night-drive/Night Drive.vtt"
    assert night.videos[1].vertical and night.videos[1].art is None
    assert [s.title for s in night.songs] == ["Artist - Night Drive"]  # no plain copy, no .wav master
    assert night.live == "night-drive/web/index.html"
    unit = shelves["lessons/course-a/unit-1"]
    assert unit.title == "Lessons · Course A · Unit 1"
    assert [v.title for v in unit.videos] == ["Chapter 2 - Second", "Chapter 10 - Last"]


def test_safe_file_refuses_hidden_outside_and_unknown(results):
    assert library.safe_file(results, "night-drive/Night Drive.mp4")
    assert library.safe_file(results, "night-drive/web/assets/app.js")
    for rel in ("night-drive/_source/take.mp4", "../outside.mp4", "night-drive/../../x.mp4", ".plexignore",
                "night-drive/notes.js", "night-drive/README.md", "", "night-drive//Night Drive.mp4"):
        assert library.safe_file(results, rel) is None, rel


@pytest.mark.parametrize("header,expected", [
    (None, None), ("bytes=0-99", (0, 99)), ("bytes=100-", (100, 999)), ("bytes=-10", (990, 999)),
    ("bytes=900-5000", (900, 999)), ("bytes=1000-", False), ("bytes=5-2", False), ("bytes=0-1,5-6", None),
    ("items=0-1", None), ("bytes=x-", None),
])
def test_parse_range(header, expected):
    assert library.parse_range(header, 1000) == expected


@pytest.fixture
def server(results, tmp_path):
    srv = library.make_server(results, port=0, host="127.0.0.1", cache=tmp_path / "cache")
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield srv.server_address[1]
    srv.shutdown()
    srv.server_close()


def get(port, path, headers=None, method="GET"):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    conn.request(method, path, headers=headers or {})
    res = conn.getresponse()
    body = res.read()
    conn.close()
    return res, body


def test_page_lists_the_library(server):
    res, body = get(server, "/")
    page = body.decode("utf-8")
    assert res.status == 200 and "text/html" in res.getheader("Content-Type")
    assert "Night Drive" in page and "Lessons · Course A · Unit 1" in page
    assert "/m/night-drive/web/index.html" in page  # the live page link
    assert "_source" not in page and "take.mp4" not in page


def test_media_is_served_in_ranges_for_phones(server, results):
    data = (results / "night-drive" / "Night Drive.mp4").read_bytes()
    res, body = get(server, "/m/night-drive/Night%20Drive.mp4", {"Range": "bytes=10-19"})
    assert res.status == 206 and body == data[10:20]
    assert res.getheader("Content-Range") == f"bytes 10-19/{len(data)}"
    assert res.getheader("Accept-Ranges") == "bytes" and res.getheader("Content-Type") == "video/mp4"
    res, body = get(server, "/m/night-drive/Night%20Drive.mp4")
    assert res.status == 200 and body == data
    res, _ = get(server, "/m/night-drive/Night%20Drive.mp4", {"Range": f"bytes={len(data)}-"})
    assert res.status == 416
    res, body = get(server, "/m/night-drive/Night%20Drive.mp4", method="HEAD")
    assert res.status == 200 and body == b"" and res.getheader("Content-Length") == str(len(data))
    res, _ = get(server, "/m/night-drive/Night%20Drive.vtt")
    assert res.status == 200 and res.getheader("Content-Type") == "text/vtt"


def test_working_files_and_escapes_are_not_served(server):
    for path in ("/m/night-drive/_source/take.mp4", "/m/../outside.mp4", "/m/night-drive/notes.js", "/nothing",
                 "/poster/night-drive/_source/take.mp4"):
        res, _ = get(server, path)
        assert res.status == 404, path


def test_library_json(server):
    import json
    res, body = get(server, "/library.json")
    data = json.loads(body)
    assert res.status == 200 and {s["rel"] for s in data} == {"night-drive", "lessons/course-a/unit-1"}


def test_agent_plist_starts_at_login_with_tools_on_path(tmp_path):
    raw = library.agent_plist(["/bin/uv", "run", "library.py"], "/opt/tools/bin:/usr/bin", tmp_path / "l.log")
    data = plistlib.loads(raw)
    assert data["Label"] == library.LABEL and data["RunAtLoad"] and data["KeepAlive"]
    assert data["EnvironmentVariables"]["PATH"].startswith("/opt/tools/bin")
    assert data["ProgramArguments"][0] == "/bin/uv"


@macos_only
def test_install_and_uninstall_agent(tmp_path, monkeypatch, results):
    agents = tmp_path / "LaunchAgents"
    monkeypatch.setattr(library, "agent_file", lambda: agents / f"{library.LABEL}.plist")
    monkeypatch.setattr(library.shutil, "which", lambda name: f"/tools/{name}")
    calls = []

    def run(cmd, **kw):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 113 if cmd[1] == "print" else 0)  # 113: no such service
    folder = tmp_path / "install" / "library"
    plist = library.install_agent(results, 8700, tmp_path / "cache", folder, run=run)
    data = plistlib.loads(plist.read_bytes())
    script = folder / "library.py"
    assert script.is_file() and script.read_text(encoding="utf-8") == Path(library.__file__).read_text(encoding="utf-8")
    args = data["ProgramArguments"]
    assert args[:4] == ["/tools/uv", "run", "--no-project", "--quiet"] and str(script) in args
    assert args[args.index("--root") + 1] == str(results) and args[args.index("--port") + 1] == "8700"
    assert any(c[:2] == ["launchctl", "bootstrap"] for c in calls)
    assert library.uninstall_agent(folder, run=run) is True
    assert not plist.exists() and not script.exists()
    assert any(c[:2] == ["launchctl", "bootout"] for c in calls)


@pytest.mark.parametrize("platform", ["win32", "linux"])
@pytest.mark.parametrize("action", ["install", "uninstall"])
def test_cli_login_item_is_refused_off_macos(mv_ws, capsys, monkeypatch, tmp_path, platform, action):
    monkeypatch.setenv("MV_INSTALL_DIR", str(tmp_path / "install"))
    monkeypatch.setattr(sys, "platform", platform)

    def never(*a, **kw):
        raise AssertionError("launchctl must not be reached off macOS")
    monkeypatch.setattr(library, "install_agent", never)
    monkeypatch.setattr(library, "uninstall_agent", never)
    assert main(["library", action]) == 2
    err = capsys.readouterr().err
    assert "macOS-only" in err and "library serve" in err and "getuid" not in err


def test_cli_status_says_how_to_start_it(mv_ws, capsys, monkeypatch):
    monkeypatch.setattr(library, "answering", lambda port, timeout=1.0: False)
    assert main(["library", "status", "--port", "8701"]) == 1
    assert "library install" in capsys.readouterr().out


@pytest.mark.parametrize("host,ok", [
    (None, True), ("192.168.1.20:8642", True), ("127.0.0.1", True), ("[::1]:8642", True), ("localhost:8642", True),
    ("studio-mac.local:8642", True), ("STUDIO-MAC.LOCAL.", True),
    ("evil.example.com", False), ("evil.example.com:8642", False), ("192.168.1.20.nip.io", False),
])
def test_trusted_host(host, ok):
    assert library.trusted_host(host) is ok


def test_a_rebound_domain_is_refused(server):
    res, body = get(server, "/library.json", {"Host": "attacker.example:8642"})
    assert res.status == 403 and b"night-drive" not in body
    res, _ = get(server, "/m/night-drive/Night%20Drive.mp4", {"Host": "attacker.example"})
    assert res.status == 403
    res, _ = get(server, "/", {"Host": "studio-mac.local:8642"})
    assert res.status == 200


@macos_only
def test_install_waits_for_the_old_copy_and_retries_the_start(tmp_path, monkeypatch, results):
    monkeypatch.setattr(library, "agent_file", lambda: tmp_path / f"{library.LABEL}.plist")
    monkeypatch.setattr(library.shutil, "which", lambda name: f"/tools/{name}")
    monkeypatch.setattr(library.time, "sleep", lambda s: None)
    seen = {"print": 0, "bootstrap": 0}

    def run(cmd, check=False, **kw):
        verb = cmd[1]
        if verb in seen:
            seen[verb] += 1
        if verb == "print":  # the old copy is still there twice, then gone
            return subprocess.CompletedProcess(cmd, 0 if seen["print"] <= 2 else 113)
        if verb == "bootstrap" and seen["bootstrap"] == 1:  # the first start fails, as launchd does mid-teardown
            raise subprocess.CalledProcessError(5, cmd)
        return subprocess.CompletedProcess(cmd, 0)
    library.install_agent(results, 8702, tmp_path / "cache", tmp_path / "lib", run=run)
    assert seen == {"print": 3, "bootstrap": 2}
