---
name: song
description: Use to make one song in the user's own Suno account through Claude in Chrome: draft the spec, fill and verify Suno's Create form, create it, compare takes, download only the take the user names (within their plan's downloads), and file a tagged MP3. A step of the make skill; also usable alone.
---

# Make a Suno song

Every command is the plugin's CLI: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" <command>`. If a
command says there is no workspace, run the make skill's Setup first. Read `references/suno-controls.md`,
`references/genre-recipes.md`, `references/originals.md` and `references/suno-ui-map.md` once per session before
step 1.

## Hard rules

1. Never click Download until the user has named the take to keep in this conversation.
2. Always run `downloaded` *before* clicking Download. If it refuses, stop. Use `--paid-extra` only when Suno's own
   "Downloads" count is above 0 and the user agreed, in this conversation, to use one of those extra downloads.
3. Never click Create on a form that failed verification (step 3).
4. Captcha ("Verify you are human") → stop, ask the user to tick it, wait for them to say done.
5. Originals only, per `originals.md`: no lines or titles from existing songs, no private references.
6. Never use unofficial Suno APIs, cookies, or captcha solvers. Suno is driven only through the user's own
   signed-in Chrome.

## 1. Draft

1. Choose a title and WebSearch `"<title>" song`; if a well-known song uses it, pick another.
2. Create the spec (it prints the spec's path; the file name is the song's `<id>`):

   ```bash
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" new --title "<title>"
   ```

3. Fill the spec's `suno:` block from the genre recipe: `model`, `styles`, `exclude_styles`, `vocal_gender`
   (omit if the recipe says unset), `weirdness`, `style_influence`, `variety`, `lyrics` with section tags. For an
   instrumental, set `instrumental: true`, leave `lyrics` empty and omit `vocal_gender`; put `instrumental` in
   `styles` and `vocals, singing, choir` in `exclude_styles`. For a set length, add `duration: <seconds>` (see the
   map's Duration Custom).
4. Validate until it prints ok:

   ```bash
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" validate <id>
   ```

5. Show the user: title · model · styles · exclude · sliders · a one-line story and the chorus. Wait for OK or
   changes. No credits are spent before this OK (filling the form in step 2 is free and may be done while waiting).

## 2. Fill (Chrome)

Invoke the `claude-in-chrome` skill, then load tools in one call:
`ToolSearch select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__tabs_create_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__computer,mcp__claude-in-chrome__read_page,mcp__claude-in-chrome__find,mcp__claude-in-chrome__form_input,mcp__claude-in-chrome__get_page_text,mcp__claude-in-chrome__javascript_tool,mcp__claude-in-chrome__browser_batch`.
`tabs_context_mcp` → `tabs_create_mcp` → `navigate` to `https://suno.com/create`. If the user is not signed in,
ask them to sign in (never type their password).
Set **every** field exactly as `suno-ui-map.md` says (Suno remembers old values): Advanced mode, model, lyrics,
styles, title, then expand More Options for exclude, vocal gender, sliders, and confirm Max Mode Off, My Taste Off,
Duration Auto (or Custom with the spec's `duration`). If the extension is not connected or a control is missing,
go to **Fallback**.

## 3. Verify

Read every field back with the map's read-back snippets and compare to the spec. An instrumental's lyrics editor
must read back empty. Lyrics are compared inside the page (embed the spec's lyrics as a JSON string; return
`{equal, diffs}`). Sliders must equal the spec value exactly; Variety's label must match. On any mismatch, re-set
that field once and re-read. Still wrong → stop and show the user a table `field | spec | page`.

## 4. Create

Install the toast watcher from the map, click Create, wait ~5 s, read `window.__toasts`.
- Captcha → hard rule 4.
- Rejected (copyright/moderation; no new rows appear): record the round without takes, show the user the message,
  propose a rewrite of the offending lines, and return to step 1.5:

  ```bash
  uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" round <id> --changes "rejected: <Suno's message>"
  ```

- Accepted: wait for both takes (~40 s to 2 min; check every ~20 s, up to 5 min), collect their URLs and durations
  as the map describes, then record them:

  ```bash
  uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" round <id> --changes "<initial | what changed>" --url <take1> --url <take2>
  ```

## 5. Listen

Tell the user the takes are ready (a table: take · length · link) and ask which to keep, or what to change. If
they want changes: edit the spec's `suno:` block, run `validate <id>`, then repeat steps 2–5.

## 6. Download

1. Record the download first (it refuses when the plan's downloads for this cycle are used up):

   ```bash
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" downloaded <id> --take-url <chosen take url>
   ```

2. Open that take's More options → Download. Select **MP3** and deselect **M4A** (it is pre-selected; formats are
   multi-select); zoom to confirm only MP3 is ticked.
3. Read the dialog's **Downloads N**. If N is 0, close the dialog, run `downloaded <id> --undo`, and stop. Tell the
   user the plugin's count ("download X of Y") and Suno's N. Suno's number is the authority.
4. Click **Unlock & Download**; wait for the dialog to close.
5. If it fails or the user cancels:

   ```bash
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" downloaded <id> --undo
   ```

## 7. Ingest

File the MP3 from the downloads folder into the song's media folder, tagged:

```bash
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" ingest <id>
```

If it reports several candidates, ask the user which file and rerun with `--file "<path>"`. If it reports none,
wait 10 s and retry once, then ask. Report the filed path and the budget line from `status`:

```bash
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" status
```

If the workspace is a git repository, commit the spec.

## Fallback: paste card

When Chrome cannot be used, print this card and let the user create and download by hand, then run step 7
(ingest dates the download from the file):

```text
Model:            <model>
Title:            <title>
Styles:           <styles>
Exclude styles:   <exclude_styles>
Vocal gender:     <vocal_gender or "—">
Weirdness:        <n>    Style Influence: <n>    Variety: <variety>
Max Mode: Off    My Taste: Off    Duration: Auto    Download format: MP3
Lyrics:
<lyrics, or "(instrumental: leave empty)">
```

## When the map is wrong

Suno changes its UI. If a control is not where the map says, find it by its visible label, get it working, and
tell the user what changed (the map ships with the plugin; suggest reporting it on the plugin's GitHub issues).
Never change the spec format to fit the UI.
