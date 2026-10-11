---
name: ingest
description: Use when a song was downloaded from Suno by hand (not through the song skill) and needs filing into the workspace, or when a song run stopped after the download.
---

# File a downloaded song

Every command is the plugin's CLI: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" <command>`.

1. Find the song's spec in the workspace's `specs/` folder (the workspace is where `doctor` says; `<id>` is the
   spec's file name). If the song has no spec, run the song skill's step 1 (Draft) to create one with the settings
   the user used, then come back.
2. File it. Only MP3 is accepted (Suno's download dialog defaults to M4A: re-download as MP3; it is free once a
   song is unlocked). Pass `--file` when the user names the file or several candidates are found:

   ```bash
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" ingest <id>
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" ingest <id> --file "<path to the mp3>"
   ```

3. Report the filed path and the budget line:

   ```bash
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" status
   ```

4. If the workspace is a git repository, commit the spec.
