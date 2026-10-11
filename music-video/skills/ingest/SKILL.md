---
name: ingest
description: Use when a song was downloaded from the song generator by hand (not through the song skill) and needs filing, tagged, into its results or album folder, or when a song run stopped after the download.
---

# File a downloaded song

Every command is the plugin's CLI: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" <command>`.

1. Find the song's spec in the workspace's `specs/` folder (the workspace is where `doctor` says; `<id>` is the
   spec's file name). If the song has no spec, run the song skill's step 1 (Draft) to create one with the settings
   the user used, then come back.
2. File it. Only MP3 is accepted (re-download the take as MP3 if another format came down; the generator's
   `workflow.md` says how). Pass `--file` when the user names the file or several candidates are found:

   ```bash
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" ingest <id>
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" ingest <id> --file "<path to the mp3>"
   ```

3. A song in an album is filed into the album's folder and its `manifest.json` is refreshed. Report the filed path
   and the budget line:

   ```bash
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" status
   ```

4. If the workspace is a git repository, commit the spec.
