"""Lifts for words the singer barely sang: song-fixes.yaml, kept with the video, applied to the song at mux and qc.

A generated take sometimes whispers a word the video needs heard. A lift raises the whole mix over that stretch (a
fader ride, so voice and band move together) through its own chain: an optional spectral denoiser, a cut above the
voice so the raised hiss stays at the song's own level, and a presence boost where words become clear. The lifted
copy is crossfaded in and out with the untouched song, so nothing outside the stretch changes.

Timing, beats and the vocal stem keep using the original song; only the audio under the picture is lifted.

    - at: 236.5          # song seconds, start of the stretch
      to: 237.9          # end of the stretch
      gain_db: 12        # the ride, 0–18 dB
      presence_db: 8     # boost at presence_hz (default 0)
      presence_hz: 2600
      hiss_cut_hz: 6500  # low-pass the lifted copy (default: off)
      denoise: true      # spectral denoiser on the lifted copy (default: false)
      fade_in: 0.2       # seconds (default 0.2)
      fade_out: 0.3
      note: "nobody planned" is whispered
"""
import hashlib
import json
from pathlib import Path

import yaml

from ..errors import MVError
from .media import need, run
from .paths import VideoPaths

KEYS = {"at", "to", "gain_db", "presence_db", "presence_hz", "hiss_cut_hz", "denoise", "fade_in", "fade_out", "note"}
MAX_GAIN_DB = 18.0
DENOISE = "afftdn=nr=20:nf=-62:tn=1"


def load_lifts(path: Path) -> list[dict]:
    """The lifts in song-fixes.yaml, checked and with defaults filled in ([] when there is no file)."""
    if not path.is_file():
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    except yaml.YAMLError as e:
        raise MVError(f"{path.name} is not valid YAML: {e}") from None
    if not isinstance(data, list):
        raise MVError(f"{path.name}: expected a list of lifts")
    lifts = []
    for i, raw in enumerate(data, 1):
        if not isinstance(raw, dict):
            raise MVError(f"{path.name}, lift {i}: expected a mapping")
        unknown = set(raw) - KEYS
        if unknown:
            raise MVError(f"{path.name}, lift {i}: unknown keys {', '.join(sorted(unknown))}")
        try:
            lift = {
                "at": float(raw["at"]), "to": float(raw["to"]),
                "gain_db": float(raw.get("gain_db", 6)),
                "presence_db": float(raw.get("presence_db", 0)),
                "presence_hz": float(raw.get("presence_hz", 2600)),
                "hiss_cut_hz": float(raw["hiss_cut_hz"]) if raw.get("hiss_cut_hz") is not None else None,
                "denoise": bool(raw.get("denoise", False)),
                "fade_in": float(raw.get("fade_in", 0.2)), "fade_out": float(raw.get("fade_out", 0.2)),
            }
        except KeyError as missing:
            raise MVError(f"{path.name}, lift {i}: {missing.args[0]} is required") from None
        except (TypeError, ValueError):
            raise MVError(f"{path.name}, lift {i}: numbers expected") from None
        if lift["to"] - lift["at"] < lift["fade_in"] + lift["fade_out"] or min(lift["fade_in"], lift["fade_out"]) <= 0:
            raise MVError(f"{path.name}, lift {i}: the stretch must be longer than its two fades (both above 0)")
        if not 0 <= lift["gain_db"] <= MAX_GAIN_DB:
            raise MVError(f"{path.name}, lift {i}: gain_db must be 0–{MAX_GAIN_DB:g}")
        lifts.append(lift)
    lifts.sort(key=lambda lift: lift["at"])
    for a, b in zip(lifts, lifts[1:]):
        if b["at"] < a["to"] - a["fade_out"]:  # one may start while the one before fades out, no earlier
            raise MVError(f"{path.name}: lifts at {a['at']:g} and {b['at']:g} overlap beyond their fades")
    return lifts


def _envelope(lift: dict) -> str:
    """0 outside the stretch, 1 inside, linear fades at both ends (an ffmpeg expression of t)."""
    return (f"clip((t-{lift['at']:.3f})/{lift['fade_in']:.3f},0,1)"
            f"*clip(({lift['to']:.3f}-t)/{lift['fade_out']:.3f},0,1)")


def _chain(lift: dict) -> str:
    steps = [DENOISE] if lift["denoise"] else []
    if lift["hiss_cut_hz"]:
        steps.append(f"lowpass=f={lift['hiss_cut_hz']:g}:p=2")
    if lift["presence_db"]:
        steps.append(f"equalizer=f={lift['presence_hz']:g}:t=q:w=0.7:g={lift['presence_db']:g}")
    gain = 10 ** (lift["gain_db"] / 20)
    steps.append(f"volume='{gain:.4f}*({_envelope(lift)})':eval=frame")
    return ",".join(steps)


def filter_graph(lifts: list[dict]) -> str:
    """The song split into the untouched copy (ducked under each stretch) and one lifted copy per stretch."""
    n = len(lifts)
    outs = "".join(f"[w{i}]" for i in range(n))
    duck = "+".join(f"({_envelope(lift)})" for lift in lifts)
    parts = [f"[0:a]asplit={n + 1}[dry]{outs}", f"[dry]volume='max(0,1-({duck}))':eval=frame[d]"]
    parts += [f"[w{i}]{_chain(lift)}[l{i}]" for i, lift in enumerate(lifts)]
    parts.append("[d]" + "".join(f"[l{i}]" for i in range(n)) + f"amix=inputs={n + 1}:normalize=0[o]")
    return ";".join(parts)


def lifted_song(paths: VideoPaths) -> Path:
    """The song to put under the picture: the original, or a lifted copy when the video has song-fixes.yaml.

    The copy is rebuilt only when the fixes or the song change (a stamp of both sits next to it).
    """
    lifts = load_lifts(paths.song_fixes)
    if not lifts:
        return paths.song
    out = paths.public / "song-lifted.wav"
    stamp = paths.public / "song-lifted.json"
    song = paths.song.stat()
    key = hashlib.sha256(json.dumps([lifts, song.st_size, song.st_mtime_ns]).encode()).hexdigest()
    if out.is_file() and stamp.is_file() and json.loads(stamp.read_text(encoding="utf-8")).get("key") == key:
        return out
    run([need("ffmpeg"), "-y", "-nostdin", "-loglevel", "error", "-i", str(paths.song),
         "-filter_complex", filter_graph(lifts), "-map", "[o]", "-c:a", "pcm_s16le", str(out)],
        f"lifting {paths.song_fixes.name}")
    stamp.write_text(json.dumps({"key": key, "lifts": lifts}, indent=1), encoding="utf-8")
    return out
