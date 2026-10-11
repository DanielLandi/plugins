---
name: song
description: Use to make one song with a song generator in the user's own account (Suno today), driven in their Chrome through Claude in Chrome: draft the spec, fill and verify the create form, create it, compare takes, download only the take the user names (within their plan's downloads), and file a tagged MP3, alone or into an album. A step of the make skill; also usable alone.
---

# Make a song

Every command is the plugin's CLI: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" <command>`. If a
command says there is no workspace, run the make skill's Setup first. Read `references/originals.md` and the
generator's references once per session before step 1.

## Generators

A spec names its song generator (`generator: suno`, the default) and keeps that generator's settings in a block
named after it (`suno:`). Everything specific to a generator, from what its controls mean to how to operate its
website, is in `references/generators/<generator>/`: `workflow.md` (what each step below means for it), `controls.md`
(what each setting means), `recipes.md` (starting points per genre) and `ui-map.md` (how to operate its website).
The steps below are the same for every generator; "the workflow" and "the map" mean that generator's files. Today's
generator is Suno: `references/generators/suno/`.

## Hard rules

1. Never click Download until the user has named the take to keep in this conversation.
2. Always run `downloaded` *before* clicking Download. If it refuses, stop. Use `--paid-extra` only when the
   generator's own remaining-downloads count is above 0 and the user agreed, in this conversation, to use one of
   those extra downloads.
3. Never click Create on a form that failed verification (step 3).
4. Captcha ("Verify you are human") → stop, ask the user to tick it, wait for them to say done.
5. Originals only, per `originals.md`: no lines or titles from existing songs, no private references.
6. Never use a generator's unofficial APIs, cookies, or captcha solvers: the generator is driven only through the
   user's own signed-in Chrome.

## 1. Draft

1. Choose a title and WebSearch `"<title>" song`; if a well-known song uses it, pick another.
2. Create the spec (it prints the spec's path; the file name is the song's `<id>`):

   ```bash
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" new --title "<title>"
   ```

3. For a song that belongs to an album (songs published together, with a `manifest.json`), add `album: <album id>`
   and, when the album credits by style, `style: <key>` (see **Albums** below).
4. Fill the generator's settings block as its `workflow.md` says (Suno: the `suno:` block, from `recipes.md`).
5. Validate until it prints ok:

   ```bash
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" validate <id>
   ```

6. Show the user the settings, a one-line story and the chorus, as the workflow says. Wait for OK or changes. No
   credits are spent before this OK (filling the form in step 2 is free and may be done while waiting).

## 2. Fill (Chrome)

Invoke the `claude-in-chrome` skill, then load tools in one call:
`ToolSearch select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__tabs_create_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__computer,mcp__claude-in-chrome__read_page,mcp__claude-in-chrome__find,mcp__claude-in-chrome__form_input,mcp__claude-in-chrome__get_page_text,mcp__claude-in-chrome__javascript_tool,mcp__claude-in-chrome__browser_batch`.
`tabs_context_mcp` → `tabs_create_mcp` → navigate to the generator's create page (its `workflow.md`). If the user
is not signed in, ask them to sign in (never type their password). Set **every** field as the workflow and the map
say. If the extension is not connected or a control is missing, go to **Fallback**.

## 3. Verify

Read every field back as the workflow says and compare to the spec. On any mismatch, re-set that field once and
re-read. Still wrong → stop and show the user a table `field | spec | page`.

## 4. Create

Create as the workflow says, watching for the generator's messages.
- Captcha → hard rule 4.
- Rejected (copyright/moderation; no new rows appear): record the round without takes, show the user the message,
  propose a rewrite of the offending lines, and return to step 1.6:

  ```bash
  uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" round <id> --changes "rejected: <the generator's message>"
  ```

- Accepted: wait for the takes (check every ~20 s, up to 5 min), collect their URLs and durations as the map
  describes, then record them:

  ```bash
  uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" round <id> --changes "<initial | what changed>" --url <take1> --url <take2>
  ```

## 5. Listen

Tell the user the takes are ready (a table: take · length · link) and ask which to keep, or what to change. If
they want changes: edit the spec's settings block, run `validate <id>`, then repeat steps 2–5.

## 6. Download

1. Record the download first (it refuses when the plan's downloads for this cycle are used up):

   ```bash
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" downloaded <id> --take-url <chosen take url>
   ```

2. Download that take as MP3, as the workflow's Download step says. If the generator's own remaining-downloads count
   is 0, close the dialog, run `downloaded <id> --undo`, and stop. Tell the user the plugin's count ("download X of
   Y") and the generator's: the generator's number is the authority.
3. If it fails or the user cancels:

   ```bash
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" downloaded <id> --undo
   ```

## 7. Ingest

File the MP3 from the downloads folder, tagged, into the song's results folder (or its album's folder, which also
refreshes the album's `manifest.json`):

```bash
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" ingest <id>
```

If it reports several candidates, ask the user which file and rerun with `--file "<path>"`. If it reports none,
wait 10 s and retry once, then ask. Report the filed path and the budget line from `status`:

```bash
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" status
```

If the workspace is a git repository, commit the spec.

## Albums

`albums/<album id>.yaml` in the workspace: `title`, `year`, optional `artist` (default: the workspace's), optional
`cover` (an image next to the file), and optional `styles:` so one album credits a different artist and album name
per style, as a compilation does:

```yaml
title: Late Night Radio
year: 2026
styles:
  synthwave:
    artist: The Late Lights
    album: Neon Hours
    genre: Synthwave
    era: 1980s
```

A song joins with `album:` and `style:`; `validate` checks the style exists. The album's folder (`<results>/albums/
<album id>/`) holds the tagged MP3s and `manifest.json` (id, title, artist, album, genre, era, kind, duration,
file, checksum, date), ready to copy to whatever site or player publishes it. Rebuild the manifest any time:

```bash
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" album <album id>
```

## Fallback: paste card

When Chrome cannot be used, print the workflow's paste card filled from the spec and let the user create and
download by hand, then run step 7 (ingest dates the download from the file).

## When the map is wrong

Generators change their UI. If a control is not where the map says, find it by its visible label, get it working, and
tell the user what changed (the map ships with the plugin; suggest reporting it on the plugin's GitHub issues).
Never change the spec format to fit the UI.
