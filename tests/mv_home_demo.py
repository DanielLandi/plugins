"""A made-up project for the home page: videos at several stages, a song with no video, a topic queued. Used by the
tests and for the README's screenshots (nothing in it is anyone's real song)."""
import json
from pathlib import Path

import yaml

from musicvideo import requests as rq
from musicvideo.spec import save_spec

LYRICS_A = """[Verse 1]
Lanterns on the water, one by one
Every wish we folded drifting from the sun

[Chorus]
Carry it over, carry it home
Little paper light, you are not alone
"""
LYRICS_B = """[Verse 1]
We wrote our names in candle smoke
And let the lake decide

[Chorus]
Float, float, the night is wide
Every flame a little ride
"""
LYRICS_C = """[Verse 1]
Grandmother taught me how to fold
A boat that holds a flame

[Chorus]
Out past the reeds where the quiet goes
Every light remembers its name
"""


def _yaml(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _video(ws, vid, step, **extra) -> Path:
    folder = ws.video_dir(vid)
    _yaml(folder / "video.yaml", {"id": vid, "step": step, "lang": "en", **extra})
    (folder / "CONCEPT.md").write_text(f"# {vid}: concept\n\n**About:** {extra.get('topic', 'a made-up song')}\n",
                                       encoding="utf-8")
    return folder


def _spec(ws, sid, title, status="drafted", rounds=None, kept=None) -> None:
    data = {"id": sid, "title": title, "kind": "original", "generator": "suno",
            "suno": {"model": "v6", "styles": "dream pop, soft female vocal", "lyrics": LYRICS_A}, "status": status}
    if rounds:
        data["rounds"] = rounds
    if kept:
        data["kept"] = kept
    save_spec(ws.specs_dir / f"{sid}.yaml", data)


def build(ws) -> dict:
    """Write the demo into the workspace; returns the ids."""
    # 1. a video whose lyric options wait for the user
    lake = _video(ws, "lantern-lake", "lyrics", topic="paper lanterns let go on a lake at midsummer")
    _yaml(lake / "lyric-options.yaml", {"rounds": [{"n": 1, "at": "2026-11-05T09:12:00", "note": "", "options": [
        {"key": "A", "title": "Carry It Over", "angle": "the wish as a journey", "lyrics": LYRICS_A},
        {"key": "B", "title": "Float", "angle": "a light, playful night out", "lyrics": LYRICS_B},
        {"key": "C", "title": "Every Light", "angle": "a family tradition, remembered", "lyrics": LYRICS_C}]}]})

    # 2. a video at the song stage: three directions, takes from two of them
    kite = _video(ws, "kite-weather", "song", topic="a windy beach day, kites everywhere")
    _yaml(kite / "directions.yaml", [
        {"name": "sunny indie pop", "why": "bright and bouncy, like the wind", "suno": {"styles": "indie pop, handclaps, bright guitars"}},
        {"name": "warm folk", "why": "an afternoon story told on the sand", "suno": {"styles": "acoustic folk, warm male vocal"}},
        {"name": "chillwave", "why": "the day remembered at dusk", "suno": {"styles": "chillwave, hazy synths"}}])
    _yaml(kite / "lyric-options.yaml", {"rounds": [], "final": {"title": "Kite Weather", "from": "A", "lyrics": LYRICS_A}})
    _spec(ws, "kite-weather", "Kite Weather", "generated", rounds=[
        {"at": "2026-11-05T10:00:00+00:00", "changes": "direction 1: sunny indie pop",
         "suno_urls": ["https://example.com/song/kite-1a", "https://example.com/song/kite-1b"]},
        {"at": "2026-11-05T10:04:00+00:00", "changes": "direction 2: warm folk",
         "suno_urls": ["https://example.com/song/kite-2a", "https://example.com/song/kite-2b"]}])

    # 3. a video in production, with drafts kept and notes waiting
    boats = _video(ws, "paper-boats", "production", topic="paper boats racing down a gutter after the rain",
                   waiting="notes on draft v2 (sections page)")
    _spec(ws, "paper-boats", "Paper Boats", "filed",
          kept={"take_url": "https://example.com/song/boats-2a", "downloaded_at": "2026-11-01T10:00:00+00:00",
                "file": "media/paper-boats.mp3"})
    review = ws.work_for("paper-boats") / "review"
    review.mkdir(parents=True)
    versions = [{"scene": "sample", "n": 1, "kind": "video", "file": "media/sample-v1.mp4", "start": 40.0,
                 "duration": 10.0, "at": "2026-11-02T09:00:00", "note": "the first chorus"},
                {"scene": "draft", "n": 1, "kind": "video", "file": "media/draft-v1.mp4", "start": 0, "duration": 30.0,
                 "at": "2026-11-03T09:00:00", "note": "first draft"},
                {"scene": "draft", "n": 2, "kind": "video", "file": "media/draft-v2.mp4", "start": 0, "duration": 30.0,
                 "at": "2026-11-04T09:00:00", "note": "Round 1: brighter gutter"}]
    (review / "versions.json").write_text(json.dumps({"video": "paper-boats", "versions": versions}), encoding="utf-8")
    (boats / "notes").mkdir()
    (boats / "notes" / "notes.json").write_text(json.dumps({"notes": [
        {"id": "n1", "n": 1, "section": "rain", "song": 3.2, "frame": 96, "render": "draft v2", "text": "more rain",
         "round": None}]}), encoding="utf-8")
    rq.video_queue(ws, "paper-boats").add("variant", {"section": "gutter", "note": "try it from above"})

    # 4. a finished video with its finals
    _video(ws, "tide-clock", "done", topic="a clock that runs on the tide")
    _spec(ws, "tide-clock", "Tide Clock", "filed")
    finals = ws.results_for("tide-clock")
    finals.mkdir(parents=True)
    for name in ("Tide Clock.mp4", "Tide Clock (vertical).mp4", "Tide Clock.srt", "thumbnail.png"):
        (finals / name).write_bytes(b"demo")
    (ws.work_for("tide-clock") / "renders").mkdir(parents=True)
    (ws.work_for("tide-clock") / "renders" / "final-silent.mp4").write_bytes(b"x" * 2048)

    # 5. a song with no video, and a topic queued on the home
    _spec(ws, "morning-ferry", "Morning Ferry", "filed")
    rq.home_queue(ws).add("new-video", {"topic": "a lighthouse keeper who collects lost radio songs",
                                        "note": "slow, warm, a little strange"})
    return {"lyrics": "lantern-lake", "song": "kite-weather", "production": "paper-boats", "done": "tide-clock",
            "alone": "morning-ferry"}
