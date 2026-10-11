---
name: make
description: Use when the user wants a music video or a song with a video ("make a music video about…", "a song and a video for…"): theme → lyrics → Suno song → timings → look → storyboard → rendered video (16:9 full song + 9:16 cut), with the user approving every stage.
---

# Make a music video

One idea → one song → one video, crafted, with the user approving each stage.

Every command is the plugin's CLI, run exactly as written from any folder:
`uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" <command>`. Run with a long timeout (or in the background,
then wait for the completion notice): renders, the board and the first `align` can take many minutes.

## Setup (first run, and whenever a command says so)

1. Check the tools and install the video engine (once, about 1.7 GB, into the OS cache folder):

   ```bash
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" doctor
   ```

   Missing tools are printed with how to install them; ask the user to install them, then run it again.
2. If doctor says there is no workspace, ask the user three things, with defaults: the artist name their songs are
   credited to; the day their Suno plan renews and how many downloads a billing cycle includes (both on their Suno
   account page; offer to read it with Claude in Chrome); and where the workspace goes (default
   `~/Movies/Music Videos`). Then:

   ```bash
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" init --artist "<name>" --billing-day <day> --download-budget <n>
   ```

   Add `--path "<folder>"` for another workspace, and `--media-dir "<folder>"` to keep the large files
   (audio, renders, deliverables) somewhere else than the video code.
3. Tell the user once: the video engine is Remotion, free for individuals and companies of up to 3 people; larger
   companies need a Remotion company licence (see the plugin's README).

Read once per session before step 1: `references/lyric-craft.md`, and the song skill's
`../song/references/suno-controls.md`, `genre-recipes.md`, `originals.md` and `suno-ui-map.md`. Read
`references/look.md` before step 5, `references/storyboard.md` before step 6, `references/studio.md` before any
scene code, and `references/checks.md` and `references/taste.md` before showing any render.

## Hard rules

1. The song skill's hard rules hold unchanged: download only a take the user named, run `downloaded` first, never
   Create on an unverified form, captchas are the user's, originals only, no unofficial Suno APIs.
2. Stop at every ✋ and wait. Ask questions with a default, so the user can just approve.
3. No production (step 7) before step 6 is approved. No final render before the draft is approved.
4. Never show a render that failed `qc` or whose frame sheet you have not looked at.
5. No image or video generation. Outside assets only CC0 or OFL, listed in the video's `SOURCES.md`.
6. Never upload or publish. Code you add is your own or MIT/CC0; transitions come only from the engine's
   `studio/transitions/` (MIT, vendored).

## Where a video lives

`uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" paths <id>` prints a video's folders as JSON. Below, `<video>`,
`<media>`, `<renders>` and `<deliver>` mean those paths; always write them out in full in commands.

- Code and documents, in `<video>`: `video.yaml` (step, checklist, gl, holds), `CONCEPT.md`, `lyrics.md`,
  `directions.yaml`, `LOOK.md`, `STORYBOARD.md`, `NOTES.md`, `JOURNAL.md`, `SOURCES.md`, `README.md`, `look.ts`,
  `video.ts`, `scenes.ts`, `cuts.ts`, `scenes/*.tsx`.
- Audio, timings, renders, deliverables, in `<media>` (outside the code folder: large files never go next to code).
- `<id>` is the song spec's id (the workspace's `specs/<id>.yaml`).

**Resuming:** read `video.yaml` (`step:`), `JOURNAL.md` and `NOTES.md`; continue at that step. At every ✋, add a
`JOURNAL.md` entry (date, what you showed, what the user said, what is next) and update `step:` and the checklist.

## 1. Concept ✋

Talk through: what the song is about, who it is for, the feeling, a genre direction, the language (default
English), the length (3–4 min). Propose one concept: a short paragraph plus the story arc (verse → pre-chorus →
chorus → bridge → final chorus). Wait for approval. Nothing is written to disk yet.

## 2. Lyrics ✋

1. Write 2–3 complete options from different angles, following `references/lyric-craft.md`. Show them in chat.
2. The user picks, combines, adds lines. Merge into one final version and show it with the title.
3. WebSearch `"<title>" song`; if a well-known song uses the title, propose another.
4. When approved, create the spec (it prints the spec's path; its file name is `<id>`) and the video folder:

   ```bash
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" new --title "<title>"
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" new-video <id>
   ```

   - Put the lyrics into the spec's `suno.lyrics` and run `validate <id>`:

     ```bash
     uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" validate <id>
     ```

   - In `<video>/index.tsx` set `TITLE` to the song's title (it is printed on the thumbnail).
   - Write `CONCEPT.md`; write `lyrics.md` (the final lyrics first, then the options under "Options considered");
     set `lang:` in `video.yaml`; `step: song`.

## 3. Song ✋

1. Write 2–3 musical directions into `<video>/directions.yaml`, each a complete `suno:` block (model, styles,
   exclude_styles, vocal_gender, weirdness, style_influence, variety) built from the genre recipes, with a
   one-line `name` and `why`. Show them as a short table; on the user's OK they are created.
2. For each direction: copy its block (with the lyrics) into the spec's `suno:`, run `validate <id>`, then run the
   song skill's steps 2 (Fill), 3 (Verify) and 4 (Create), recording the round with
   `--changes "direction <n>: <name>"`.
3. Show one table of every take (direction · take · length · link). The user listens and names one, or asks for
   another round (new or changed directions; repeat 2).
4. Copy the chosen direction's block into the spec's `suno:` (so the spec describes the kept take), run
   `validate <id>`, then the song skill's step 6 (Download) and step 7 (Ingest). `step: timing`.

## 4. Timing ✋

1. Word timings (the first run on a machine installs the alignment models; give it time). A new take or a
   language change is detected automatically; `--force` redoes everything by hand. Then the song map and a
   karaoke preview:

   ```bash
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" align <id> --lang <lang>
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" analyze <id>
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" preview <id> --open
   ```

2. Show the user: the align summary (repairs, unsure words with times, possibly missing lines), the tempo and the
   sections, and ask them to watch the preview.
   - Bad words → write `<media>/timing-fixes.yaml` entries (`- at: "1:13"` / `word: thunder` / `shift: 0.2`, or
     `start:`/`end:`), re-run align and preview.
   - A word sung one way but written another (a number sung as words: "nine-to-five" shown as "9-to-5") → a
     `timing-fixes.yaml` entry `- word: Nine-to-five` / `show: "9-to-5"` (every occurrence; add `at:` for one).
     Only the text in timing.json and the subtitles changes; the times stay. Re-run align and preview.
   - A line Suno did not sing (or sang differently) → write `<media>/lyrics-as-sung.txt` with the lyrics as sung
     (same tags), re-run align, analyze and preview.
   - More than 10% unsure words → offer: fix words, use as-sung lyrics, or pick another take.
3. On approval: `step: look`.

## 5. Look ✋

Follow `references/look.md`: 2–3 directions, each a `LOOK.md` section and a look composition, 3–4 real 16:9
style frames plus one 9:16 chorus frame each, shown side by side on one sheet. Iterate until the user approves one
(or a merge). Then: final `LOOK.md`, `look.ts` values, remove the losing look code. `step: sample`.

## 6. Sample, storyboard, subtitles ✋ (the go signal)

Follow `references/storyboard.md`:
1. `STORYBOARD.md`, `scenes.ts` (one scene per section) and `cuts.ts` (the transition board).
2. Set `video.ts` `ranges.sample` (≈10 s: the end of the pre-chorus into the first chorus lines, ending on a
   bar line) and `ranges.vertical` (30–60 s around the chorus, hook first).
3. Build the scenes the sample covers, for real, following `references/studio.md`.
4. Run the transition board until every cut passes; read every panel:

   ```bash
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" board <id>
   ```

5. Render the sample twice (with word subtitles and clean), add the song, check both, and look at both sheets:

   ```bash
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" render <id> <id>-sample "<renders>/sample-words-silent.mp4" --muted '--props={"lyrics":"words"}'
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" render <id> <id>-sample "<renders>/sample-clean-silent.mp4" --muted '--props={"lyrics":"none"}'
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" mux "<renders>/sample-words-silent.mp4" --spec <id> --excerpt <from>-<to> --out "<renders>/sample-words.mp4"
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" mux "<renders>/sample-clean-silent.mp4" --spec <id> --excerpt <from>-<to> --out "<renders>/sample-clean.mp4"
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" qc "<renders>/sample-words.mp4" --spec <id> --excerpt <from>-<to> --size 1920x1080
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" qc "<renders>/sample-clean.mp4" --spec <id> --excerpt <from>-<to> --size 1920x1080
   ```

   Add a `--hold a-b` to each qc for every designed hold in `video.yaml`: song time, the same values as there,
   even though these are excerpts (qc shifts them into the clip).

6. Show together: the storyboard (as text), the board panels, both samples. Ask the subtitles question with a
   default: none / whole lines / word highlight, and the style. On approval: set `subtitles` in `look.ts` and
   `video.yaml`; `step: production`.

## 7. Production ✋

1. For every storyboard section without real code, dispatch a scene agent with the brief template in
   `references/studio.md` (at most 4 at a time; they write only `scenes/<section>.tsx` and render stills only).
   Review each agent's stills yourself; re-brief any scene that drifts from `LOOK.md`.
2. The board must pass (`board <id>`) and the code must type-check:

   ```bash
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" typecheck <id>
   ```

3. Draft at full scale (some transitions break at `--scale=0.5`), add the song, check it, and look at the sheet:

   ```bash
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" render <id> <id>-full "<renders>/draft-v<n>-silent.mp4" --muted
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" mux "<renders>/draft-v<n>-silent.mp4" --spec <id> --out "<renders>/draft-v<n>.mp4"
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" qc "<renders>/draft-v<n>.mp4" --spec <id> --size 1920x1080
   ```

   Add `--hold a-b` to qc for every designed hold in `video.yaml`. Fix and re-render on any problem. Delete the
   previous draft once this one is shown.
4. Show the draft. Number the user's notes in `NOTES.md` under "Round <n>". Sort each into error or taste. The
   next version answers every note in `NOTES.md` (what changed, or why not; never just "addressed"). Changed
   sections can come back first as clips (`--frames=a-b`); a clip also goes through `mux --excerpt` and
   `qc --excerpt` before it is shown (hard rule 4). For an error no check caught, propose a new entry for
   `references/checks.md`; for taste, a line for the workspace's `taste.md` (see `references/taste.md`); add them
   only with the user's OK.
5. Motion blur, when the look calls for it (smooth camera moves, fast objects): render with sub-frames and average
   them (32 samples, a 180° shutter); it takes several times longer than a plain render, so offer it for the final:

   ```bash
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" blur <id> <id>-full "<renders>/final-blur-silent.mp4" --samples=32
   ```

6. On approval: `step: delivery`.

## 8. Delivery

Create `<deliver>`, then render, add the song, check, and render the thumbnail:

```bash
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" render <id> <id>-full "<renders>/final-silent.mp4" --muted --crf=18
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" mux "<renders>/final-silent.mp4" --spec <id> --out "<deliver>/<Title>.mp4"
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" qc "<deliver>/<Title>.mp4" --spec <id> --size 1920x1080
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" render <id> <id>-vertical "<renders>/vertical-silent.mp4" --muted --crf=18
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" mux "<renders>/vertical-silent.mp4" --spec <id> --excerpt <from>-<to> --out "<deliver>/<Title> (vertical).mp4"
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" qc "<deliver>/<Title> (vertical).mp4" --spec <id> --excerpt <from>-<to> --size 1080x1920
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" still <id> <id>-thumb "<deliver>/thumbnail.png" --frame=<the strongest frame>
```

(Use `final-blur-silent.mp4` from step 7 in place of the plain render when the final is motion-blurred.) Add the
same `--hold a-b` flags as the draft to the qc commands. Copy `<media>/lyrics.lrc`, `.srt` and `.vtt` to
`<deliver>/<Title>.lrc`, `.srt` and `.vtt` (players load them next to `<Title>.mp4`) and `<video>/README.md` to
`<deliver>/README.md`.

Look at both sheets and the thumbnail. Finish `README.md` and `SOURCES.md`. Open the deliverables for the user.
If the workspace is a git repository, commit the spec and `<video>` (never the media). `step: done`. Uploading
is the user's.
