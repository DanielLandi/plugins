"""Fixtures for the music-video tests (loaded by conftest.py through pytest_plugins)."""
import pytest


def valid_spec(**overrides) -> dict:
    data = {
        "id": "night-drive",
        "title": "Night Drive",
        "kind": "original",
        "suno": {
            "model": "v6",
            "styles": "synthwave, male vocal, warm analog pads",
            "exclude_styles": "acoustic guitar",
            "vocal_gender": "male",
            "weirdness": 30,
            "style_influence": 75,
            "variety": "normal",
            "lyrics": "[Verse 1]\nHeadlights on the empty road tonight\n\n\n[Chorus]\nKeep on driving to the dawn\n",
        },
        "status": "drafted",
    }
    data.update(overrides)
    return data


@pytest.fixture(autouse=True)
def mv_isolated(tmp_path, monkeypatch):
    """No test reads or writes the real workspace pointer, settings file or engine cache."""
    monkeypatch.delenv("MUSIC_VIDEO_HOME", raising=False)
    monkeypatch.setenv("MV_SETTINGS", str(tmp_path / "settings.json"))
    monkeypatch.setenv("MV_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MV_INSTALL_DIR", str(tmp_path / "install"))


@pytest.fixture
def mv_ws(tmp_path, monkeypatch):
    from musicvideo.workspace import init_workspace, load_workspace
    home = tmp_path / "My Videos é"
    monkeypatch.setenv("MUSIC_VIDEO_HOME", str(home))
    monkeypatch.setenv("MV_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MV_SETTINGS", str(tmp_path / "settings.json"))
    (tmp_path / "Downloads").mkdir()
    init_workspace(home, artist="Test Artist", billing_day=15, download_budget=20,
                   results_dir=tmp_path / "My Results é")
    cfg = home / "config.yaml"
    text = cfg.read_text(encoding="utf-8").replace("~/Downloads", str(tmp_path / "Downloads"))
    cfg.write_text(text + f"work_dir: {tmp_path / 'My Work é'}\n", encoding="utf-8")
    return load_workspace()


@pytest.fixture
def write_spec(mv_ws):
    from musicvideo.spec import save_spec

    def _write(**overrides):
        data = valid_spec(**overrides)
        path = mv_ws.specs_dir / f"{data['id']}.yaml"
        save_spec(path, data)
        return path

    return _write


@pytest.fixture
def make_mp3():
    import shutil
    import subprocess
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not installed")

    def _make(path, comment=None, cover=None, seconds=1):
        path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                        "-t", str(seconds), "-q:a", "9", "-y", str(path)], check=True)
        if comment or cover:
            from mutagen.id3 import APIC, COMM, ID3, ID3NoHeaderError
            try:
                tags = ID3(path)
            except ID3NoHeaderError:
                tags = ID3()
            if comment:
                tags.add(COMM(encoding=3, lang="eng", desc="", text=comment))
            if cover:
                tags.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=cover))
            tags.save(path)
        return path

    return _make


@pytest.fixture
def filed_song(mv_ws, write_spec):
    """A filed spec whose media MP3 is a generated tone. Call it; returns (spec_id, mp3_path)."""
    import shutil
    import subprocess
    from pathlib import Path
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not installed")

    def _make(seconds: float = 4.0, freq: int = 220, **overrides):
        mp3 = mv_ws.results_for("night-drive") / "Test Artist - Night Drive.mp3"
        rel = str(mp3)
        mp3.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i",
                        f"sine=frequency={freq}:sample_rate=44100:duration={seconds}",
                        "-ac", "1", "-c:a", "libmp3lame", "-b:a", "128k", "-y", str(mp3)], check=True)
        kept = {"take_url": "https://suno.com/song/abc", "downloaded_at": "2026-10-01T10:00:00-07:00",
                "file": rel, "filed_at": "2026-10-01T10:01:00-07:00"}
        path = write_spec(**({"status": "filed", "kept": kept} | overrides))
        return path.stem, mp3

    return _make


@pytest.fixture
def requires_ffmpeg():
    """Skip where ffmpeg and ffprobe are not on PATH (CI runners may not have them)."""
    import shutil
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        pytest.skip("ffmpeg not installed")
