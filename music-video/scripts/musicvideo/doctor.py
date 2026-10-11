"""Check the tools the plugin needs and install the video engine's packages into the install folder."""
import re
import shutil
import subprocess

from . import studio
from .errors import MVError
from .workspace import load_workspace, workspace_home

NEEDS = {
    "uv": "https://docs.astral.sh/uv/getting-started/installation/",
    "node": "https://nodejs.org (version 20 or newer)",
    "ffmpeg": "https://ffmpeg.org/download.html (macOS: brew install ffmpeg)",
    "ffprobe": "comes with ffmpeg",
}


def _node_major() -> int:
    out = subprocess.run([shutil.which("node"), "--version"], capture_output=True, text=True, encoding="utf-8").stdout
    m = re.match(r"v(\d+)", out.strip())
    return int(m.group(1)) if m else 0


def run_doctor(install: bool = True) -> int:
    missing = [f"missing {tool}: {how}" for tool, how in NEEDS.items() if not shutil.which(tool)]
    if shutil.which("node") and _node_major() < 20:
        missing.append("Node is older than 20: install a current LTS from https://nodejs.org")
    for line in missing:
        print(line)
    try:
        ws = load_workspace()
        print(f"ok   workspace {ws.home} (results in {ws.results_dir}, work in {ws.work_dir})")
    except MVError as e:
        if (workspace_home() / "config.yaml").is_file():
            print(f"fix  workspace: {e}")
        else:
            print(f"todo workspace: none at {workspace_home()}; run music-video init --artist \"<name>\"")
    print("note the song steps need Chrome with the Claude in Chrome extension, signed in to your Suno account")
    if missing:
        return 1
    if studio.migrate_old_runtime():
        print(f"ok   moved the engine from the cache to {studio.runtime_dir()}")
    rt = studio.sync_runtime()
    if studio.is_installed(rt):
        print(f"ok   video engine installed in {rt}")
    elif install:
        print(f"installing the video engine's packages in {rt} (about 1.7 GB, once)…", flush=True)
        studio.install(rt)
        print("ok   video engine installed")
    else:
        print("todo video engine not installed: run music-video doctor")
        return 1
    return 0
