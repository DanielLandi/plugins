"""Check the tools the plugin needs and install the video engine's packages into the install folder."""
import re
import shutil
import subprocess

from . import studio
from .errors import MVError
from .workspace import config_path, install_dir, load_workspace, workspace_home

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


def _size(n: int) -> str:
    return f"{n / 1e9:.1f} GB" if n >= 1e9 else f"{n / 1e6:.0f} MB"


def _prune_engines() -> None:
    """Engines of plugin checkouts that are gone (a removed worktree): removed, one line each. Never fatal."""
    try:
        pruned = studio.prune_engines()
    except (OSError, MVError) as e:
        print(f"note could not look for engines of removed checkouts: {e}")
        return
    for p in pruned:
        if p.removed:
            print(f"ok   removed the engine of the removed checkout {p.checkout}: freed {_size(p.freed)} ({p.engine})"
                  + (f"; {p.why}" if p.why else ""))
        else:
            print(f"note kept the engine of the removed checkout {p.checkout} ({p.engine}): {p.why}")


def run_doctor(install: bool = True) -> int:
    missing = [f"missing {tool}: {how}" for tool, how in NEEDS.items() if not shutil.which(tool)]
    if shutil.which("node") and _node_major() < 20:
        missing.append("Node is older than 20: install a current LTS from https://nodejs.org")
    for line in missing:
        print(line)
    try:
        ws = load_workspace()
        print(f"ok   workspace {ws.home} (results in {ws.results_dir}, work in {ws.work_dir})")
        if ws.lane:
            print(f"ok   worktree {ws.lane} of {ws.main_home}: work in {ws.work_root}, video finals in {ws.finals_root}")
    except MVError as e:
        if config_path(workspace_home()).is_file():
            print(f"fix  workspace: {e}")
        else:
            print(f"todo workspace: none at {workspace_home()}; run music-video init --artist \"<name>\"")
    print("note the song steps need Chrome with the Claude in Chrome extension, signed in to your Suno account")
    if missing:
        return 1
    # Before the lock: the lock file lives in the engine folder, and the move only runs while that folder is absent.
    if studio.migrate_old_runtime():
        print(f"ok   moved the engine from the cache to {install_dir() / 'engine'}")
    _prune_engines()
    checkout = studio.plugin_checkout()
    with studio.engine_lock(studio.runtime_dir()) as rt:
        try:
            studio.refuse_other_source(rt)
        except MVError as e:
            print(f"fix  {e}")
            return 1
        studio.sync_runtime(dest=rt)
        studio.touch_owner(rt)
        if not studio.is_installed(rt) and (seed := studio.seed_modules(rt)):
            print(f"ok   video engine seeded from {seed}")
        if studio.is_installed(rt):
            print(f"ok   video engine for the checkout {checkout} in {rt}" if checkout
                  else f"ok   video engine installed in {rt}")
        elif install:
            print(f"installing the video engine's packages in {rt} (about 1.7 GB, once)…", flush=True)
            studio.install(rt)
            print("ok   video engine installed")
        else:
            print("todo video engine not installed: run music-video doctor")
            return 1
    return 0
