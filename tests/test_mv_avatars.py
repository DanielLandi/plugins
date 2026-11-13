"""The CC0 VRoid sample avatars: downloaded into the install folder with pinned checksums, never bundled, and never
a reason for doctor to fail."""
import errno
import hashlib
import http.client
import io
import re
import time
import zipfile
from pathlib import Path
from urllib.error import URLError

import pytest

from musicvideo import avatars
from musicvideo.errors import MVError


def _zip(member: str, data: bytes) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(member, data)
    return buf.getvalue()


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


@pytest.fixture
def fake(monkeypatch):
    """Two small stand-in avatars served by a fake fetch (no network), pinned like the real ones."""
    served: dict[str, bytes] = {}
    entries = []
    for n in (1, 2):
        vrm = b"glTF" + bytes([n]) * 3000
        z = _zip(f"Sample_{n}.vrm", vrm)
        url = f"https://example.org/files/sample_{n}.zip"
        served[url] = z
        entries.append(avatars.Avatar(key=f"test-sample-{n}", file=f"test-sample-{n}.vrm", name=f"Test {n}",
                                      zip_url=url, zip_sha256=_sha(z), member=f"Sample_{n}.vrm", sha256=_sha(vrm),
                                      size=len(vrm), page="https://example.org/content/samples"))
    calls = []

    def fetch(url, dest):
        calls.append(url)
        if url not in served:
            raise URLError("offline")
        dest.write_bytes(served[url])

    monkeypatch.setattr(avatars, "AVATARS", tuple(entries))
    monkeypatch.setattr(avatars, "fetch_url", fetch)
    fetch.served, fetch.calls, fetch.entries = served, calls, entries
    return fetch


def test_pinned_avatars_are_the_four_samples():
    real = avatars.PINNED
    assert [a.key for a in real] == [f"vroid-sample-{n}" for n in range(1, 5)]
    for a in real:
        assert re.fullmatch(r"[0-9a-f]{64}", a.sha256) and re.fullmatch(r"[0-9a-f]{64}", a.zip_sha256)
        assert a.zip_url.startswith("https://opengameart.org/") and a.file == f"{a.key}.vrm" and a.size > 1_000_000
    assert len({a.sha256 for a in real}) == 4


def test_install_downloads_checks_and_writes_sources(fake):
    lines = avatars.install()
    folder = avatars.avatar_dir()
    for a in fake.entries:
        assert avatars.state(a) == "ok"
        assert (folder / a.file).read_bytes().startswith(b"glTF")
    sources = (folder / "SOURCES.md").read_text(encoding="utf-8")
    assert "CC0" in sources and "https://example.org/content/samples" in sources
    assert not list(folder.glob("*.part")) and not list(folder.glob(".*.part"))
    assert any("test-sample-1.vrm" in line for line in lines)
    fake.calls.clear()
    avatars.install()  # already there: nothing is downloaded again
    assert fake.calls == []


def test_zip_checksum_mismatch_keeps_nothing(fake):
    a = fake.entries[0]
    fake.served[a.zip_url] = _zip(a.member, b"glTF tampered")
    with pytest.raises(MVError, match="test-sample-1.vrm"):
        avatars.install()
    assert avatars.state(a) == "missing"
    assert not [p for p in avatars.avatar_dir().iterdir() if p.name.endswith(".part")]
    assert avatars.state(fake.entries[1]) == "ok"  # one bad download never stops the others


def test_bad_file_is_replaced(fake):
    a = fake.entries[0]
    folder = avatars.avatar_dir()
    folder.mkdir(parents=True)
    (folder / a.file).write_bytes(b"glTF half a fi")  # an interrupted copy
    assert avatars.state(a) == "bad"
    avatars.install()
    assert avatars.state(a) == "ok"
    (folder / a.file).write_bytes(b"x" * a.size)  # right size, wrong content
    assert avatars.state(a) == "bad"


def test_add_accepts_a_matching_vrm_or_zip_and_refuses_others(fake, tmp_path):
    a, b = fake.entries
    vrm = tmp_path / "Downloads" / "whatever name.vrm"
    vrm.parent.mkdir()
    with zipfile.ZipFile(io.BytesIO(fake.served[a.zip_url])) as z:
        vrm.write_bytes(z.read(a.member))
    assert avatars.add(vrm) == a and avatars.state(a) == "ok"
    zpath = tmp_path / "Downloads" / "b.zip"
    zpath.write_bytes(fake.served[b.zip_url])
    assert avatars.add(zpath) == b and avatars.state(b) == "ok"
    other = tmp_path / "Downloads" / "mine.vrm"
    other.write_bytes(b"glTF someone else")
    with pytest.raises(MVError, match="not one of"):
        avatars.add(other)
    with pytest.raises(MVError, match="does not exist"):
        avatars.add(tmp_path / "nope.vrm")


def _doctor_env(monkeypatch, tmp_path):
    from musicvideo import doctor, studio
    monkeypatch.setattr(doctor.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(doctor, "_node_major", lambda: 22)
    rt = studio.runtime_dir()
    (rt / "node_modules").mkdir(parents=True)
    monkeypatch.setattr(studio, "sync_runtime", lambda dest: dest)
    monkeypatch.setattr(studio, "is_installed", lambda rt: True)
    return doctor


def test_doctor_offline_keeps_exit_code(fake, monkeypatch, tmp_path, capsys):
    doctor = _doctor_env(monkeypatch, tmp_path)
    fake.served.clear()  # offline
    assert doctor.run_doctor() == 0
    out = capsys.readouterr().out
    assert "music-video avatars install" in out and "Traceback" not in out
    assert all(avatars.state(a) == "missing" for a in fake.entries)


def test_doctor_downloads_them(fake, monkeypatch, tmp_path, capsys):
    doctor = _doctor_env(monkeypatch, tmp_path)
    assert doctor.run_doctor() == 0
    assert all(avatars.state(a) == "ok" for a in fake.entries)
    assert "avatars" in capsys.readouterr().out


def test_doctor_no_install_only_reports(fake, monkeypatch, tmp_path, capsys):
    doctor = _doctor_env(monkeypatch, tmp_path)
    assert doctor.run_doctor(install=False) == 0
    assert doctor.run_doctor(avatars=False) == 0
    assert fake.calls == []
    assert "music-video avatars install" in capsys.readouterr().out


def test_cli_status_install_add(fake, tmp_path, capsys):
    from musicvideo.cli import main
    assert main(["avatars"]) == 0
    assert "missing" in capsys.readouterr().out
    assert main(["avatars", "install"]) == 0
    capsys.readouterr()
    assert main(["avatars", "status"]) == 0
    assert len(re.findall(r"(?m)^ok\s+test-sample-\d\.vrm", capsys.readouterr().out)) == 2
    assert main(["avatars", "add"]) == 2  # add needs a file


def test_render_stops_when_avatar_missing(fake, mv_ws):
    vdir = mv_ws.video_dir("duel")
    (vdir / "bakeoff").mkdir(parents=True)
    (vdir / "bakeoff" / "vrm.tsx").write_text(
        "import a from '@mv/avatars/test-sample-1.vrm';\nimport b from \"@mv/avatars/test-sample-2.vrm\";\n"
        "import mine from './hero.vrm';\n", encoding="utf-8")
    (vdir / "index.tsx").write_text("export const x = 1;\n", encoding="utf-8")
    assert avatars.imported(vdir) == {"test-sample-1.vrm", "test-sample-2.vrm"}
    with pytest.raises(MVError, match=r"test-sample-1\.vrm.*music-video avatars install"):
        avatars.check_video(vdir)
    avatars.install()
    avatars.check_video(vdir)  # all there: no error
    (vdir / "bakeoff" / "vrm.tsx").write_text("import a from '@mv/avatars/nobody.vrm';\n", encoding="utf-8")
    with pytest.raises(MVError, match="nobody.vrm"):
        avatars.check_video(vdir)


def test_a_video_without_avatars_needs_none(mv_ws):
    vdir = mv_ws.video_dir("plain")
    vdir.mkdir(parents=True)
    (vdir / "index.tsx").write_text("import x from './car.glb';\n", encoding="utf-8")
    assert avatars.imported(vdir) == set()
    avatars.check_video(vdir)


def test_a_video_using_avatars_credits_them(fake, mv_ws):
    vdir = mv_ws.video_dir("duel")
    vdir.mkdir(parents=True)
    (vdir / "scene.tsx").write_text("import a from '@mv/avatars/test-sample-1.vrm';\n", encoding="utf-8")
    (vdir / "SOURCES.md").write_text("| Asset | Source | Licence |\n|---|---|---|\n", encoding="utf-8")
    avatars.install()
    avatars.check_video(vdir)
    text = (vdir / "SOURCES.md").read_text(encoding="utf-8")
    assert "test-sample-1.vrm" in text and "CC0" in text
    avatars.check_video(vdir)
    assert (vdir / "SOURCES.md").read_text(encoding="utf-8") == text  # once


@pytest.mark.parametrize("error", [http.client.IncompleteRead(b"glTF half"), http.client.RemoteDisconnected("gone")])
def test_a_broken_connection_is_offline_not_a_traceback(fake, monkeypatch, error):
    a = fake.entries[0]

    def broken(url, dest):
        dest.write_bytes(b"PK half a zip")  # the connection drops mid-download
        raise error
    monkeypatch.setattr(avatars, "fetch_url", broken)
    with pytest.raises(MVError, match=r"test-sample-1\.vrm: could not download"):
        avatars.download(a)
    assert not [p for p in avatars.avatar_dir().iterdir() if p.name.endswith(".part")]
    with pytest.raises(MVError):
        avatars.install()  # every avatar is tried, and the failure is one MVError


@pytest.mark.parametrize("kind", ["vrm", "zip"])
def test_add_on_a_full_disk_says_so_in_one_line_and_leaves_nothing(fake, monkeypatch, tmp_path, kind):
    a = fake.entries[0]
    src = tmp_path / f"mine.{kind}"
    if kind == "zip":
        src.write_bytes(fake.served[a.zip_url])
    else:
        with zipfile.ZipFile(io.BytesIO(fake.served[a.zip_url])) as z:
            src.write_bytes(z.read(a.member))

    def full(path, data=None, *args, **kwargs):
        Path(path).write_text("half", encoding="utf-8")
        raise OSError(errno.ENOSPC, "No space left on device")
    monkeypatch.setattr(avatars.shutil, "copyfile", lambda s, d: full(d))
    monkeypatch.setattr(Path, "write_bytes", lambda self, data: full(self))
    with pytest.raises(MVError, match=r"could not add .*No space left on device"):
        avatars.add(src)
    folder = avatars.avatar_dir()
    assert not [p for p in folder.iterdir() if p.name.endswith(".part")]
    assert avatars.state(a) == "missing"


def test_doctor_waits_a_day_after_a_failed_download(fake, monkeypatch, tmp_path, capsys):
    doctor = _doctor_env(monkeypatch, tmp_path)
    fake.served_backup = dict(fake.served)
    fake.served.clear()  # the mirror is down
    doctor.run_doctor()
    assert len(fake.calls) == 2
    fake.calls.clear()
    capsys.readouterr()
    assert doctor.run_doctor() == 0  # the next run does not wait on the dead mirror again
    out = capsys.readouterr().out
    assert fake.calls == []
    note = [line for line in out.splitlines() if "avatar" in line]
    assert len(note) == 1 and "music-video avatars install" in note[0] and "24 h" in note[0]
    fake.served.update(fake.served_backup)  # the mirror is back: an explicit install always tries
    avatars.install()
    assert all(avatars.state(a) == "ok" for a in fake.entries)
    assert not (avatars.avatar_dir() / avatars.FAILED).exists()  # a success clears the memory


def test_doctor_tries_again_after_a_day(fake, monkeypatch, tmp_path):
    doctor = _doctor_env(monkeypatch, tmp_path)
    fake.served_backup = dict(fake.served)
    fake.served.clear()
    doctor.run_doctor()
    fake.served.update(fake.served_backup)
    real = time.time()
    monkeypatch.setattr(avatars.time, "time", lambda: real + 25 * 3600)
    doctor.run_doctor()
    assert all(avatars.state(a) == "ok" for a in fake.entries)
