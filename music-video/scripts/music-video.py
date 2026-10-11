#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "mutagen>=1.47",
#   "numpy>=1.26",
#   "pyyaml>=6.0",
# ]
# ///
"""music-video: songs and music videos from your own Suno account. Run `--help` for the commands."""
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # the plugin folder is replaced on update: never write into it
sys.path.insert(0, str(Path(__file__).resolve().parent))

from musicvideo.cli import main  # noqa: E402

sys.exit(main())
