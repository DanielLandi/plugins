# /// script
# requires-python = ">=3.12"
# dependencies = ["stable-ts==2.19.1", "demucs==4.1.0", "beat-this==1.1.0", "soundfile>=0.13"]
# ///
"""The machine-learning half of music-video's video commands, run in its own cached uv environment:

    uv run --script worker.py timing <song.mp3> <align-input.txt> <lang> <out_dir>
    uv run --script worker.py beats <song.mp3> <out.json>

Kept apart so the song tooling never installs torch and tests never load a model.
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MODEL = "large-v3"


def _words(result) -> list[dict]:
    return [{"word": w.word.strip(), "start": round(w.start, 3), "end": round(w.end, 3),
             "prob": round(w.probability or 0.0, 3)}
            for seg in result.segments for w in seg.words]


def _separate(song: Path, vocals: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        for device in ("mps", "cpu"):
            cmd = [sys.executable, "-m", "demucs", "--two-stems=vocals", "-n", "htdemucs", "-d", device,
                   "-o", tmp, str(song)]
            if subprocess.run(cmd).returncode == 0:
                break
        else:
            sys.exit("demucs failed on both mps and cpu")
        shutil.move(str(next(Path(tmp).glob("htdemucs/*/vocals.wav"))), vocals)


def timing(song: str, lyrics_txt: str, lang: str, out_dir: str) -> None:
    out = Path(out_dir)
    vocals = out / "vocals.wav"
    if not vocals.exists():
        _separate(Path(song), vocals)
    import stable_whisper

    model = stable_whisper.load_model(MODEL, device="cpu")
    aligned = model.align(str(vocals), Path(lyrics_txt).read_text(encoding="utf-8"), language=lang, original_split=True)
    (out / "aligned.json").write_text(json.dumps({"words": _words(aligned)}), encoding="utf-8")
    if not (out / "transcript.json").exists():
        heard = model.transcribe(str(vocals), language=lang, word_timestamps=True, vad=True)
        (out / "transcript.json").write_text(json.dumps({"words": _words(heard)}), encoding="utf-8")


def beats(song: str, out_json: str) -> None:
    import torch
    from beat_this.inference import File2Beats

    devices = ["mps", "cpu"] if torch.backends.mps.is_available() else ["cpu"]
    for device in devices:
        try:
            found, down = File2Beats(checkpoint_path="final0", device=device, dbn=False)(song)
            break
        except RuntimeError:
            if device == devices[-1]:
                raise
    Path(out_json).write_text(json.dumps({"beats": [round(float(b), 3) for b in found],
                                          "downbeats": [round(float(d), 3) for d in down]}), encoding="utf-8")


if __name__ == "__main__":
    command, *rest = sys.argv[1:]
    {"timing": timing, "beats": beats}[command](*rest)
