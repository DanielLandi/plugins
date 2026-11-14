---
name: make
description: Use when the user wants a music video or a song with a video ("make a music video about…", "a song and a video for…"): theme → lyrics → a song from their own song generator account (Suno today) → timings → look → storyboard → rendered video (16:9 full song + 9:16 cut, optionally a live web page), with the user approving every stage.
---

# Make a music video

One idea → one song → one video, crafted, with the user approving each stage.

Every command is the plugin's CLI, run exactly as written from any folder:
`uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" <command>`. Run with a long timeout (or in the background,
then wait for the completion notice): renders, the board and the first `align` can take many minutes.

## Setup (first run, and whenever a command says so)

1. Check the tools and install the video engine (once, about 2 GB, into the install folder:
   `~/Library/Application Support/music-video/` on macOS):

   ```bash
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" doctor
   ```

   Missing tools are printed with how to install them; ask the user to install them, then run it again.
2. If doctor says there is no workspace, ask the user three things, with defaults: the artist name their songs are
   credited to; the day their song generator plan renews and how many downloads a billing cycle includes (both on
   their account page with the generator; offer to read it with Claude in Chrome); where the project folder goes (default
   `~/Documents/Music Videos`: specs and video code, small) and where finished videos go (default
   `~/Movies/Music Videos`). Then:

   ```bash
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" init --artist "<name>" --billing-day <day> --download-budget <n>
   ```

   Add `--path "<folder>"` for another project folder and `--results-dir "<folder>"` for another results folder.
   Working files (timings, renders, checks) go to the OS cache folder; `work_dir` in `config.yaml` moves them.
3. Tell the user once: the video engine is Remotion, free for individuals and companies of up to 3 people; larger
   companies need a Remotion company licence (see the plugin's README).

Read once per session before step 1: `references/lyric-craft.md`, and the song skill's
`../song/references/originals.md` and the generator's references (`../song/references/generators/suno/`). Read
`references/look.md` before step 5 (and `references/bakeoff.md` when the video has characters),
`references/storyboard.md` before step 6, `references/studio.md` and
`references/animation.md` before any scene code, `references/shot-design.md` before keying any camera move, and `references/checks.md` and `references/taste.md` before showing any render.

## Hard rules

1. The song skill's hard rules hold unchanged: download only a take the user named, run `downloaded` first, never
   Create on an unverified form, captchas are the user's, originals only, no unofficial generator APIs.
2. Stop at every ✋ and wait. Ask questions with a default, so the user can just approve.
3. No production (step 7) before step 6 is approved. No final render before the draft is approved.
4. Never show a render that failed `qc` or whose frame sheet you have not looked at.
5. No image or video generation. Outside assets only CC0 or OFL, listed in the video's `SOURCES.md`.
6. Never upload or publish. Code you add is your own or MIT/CC0; transitions come only from the engine's
   `studio/transitions/` (MIT, vendored).

## Where a video lives

`uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" paths <id>` prints a video's folders as JSON. Below, `<video>`,
`<work>`, `<public>`, `<renders>`, `<results>` and `<web>` mean those paths; always write them out in full in
commands.

In a git worktree of the project, `paths` prints that worktree's own folders (and a `lane` key). The song stays in
the main results folder. Song downloads still count against the one budget. The first command that needs a video's
work folder there copies the main checkout's timings into it (it prints one line saying so): do not re-run `align`
or `analyze` unless the timings change.

- Code and documents, in `<video>`: `video.yaml` (step, waiting, topic, checklist, gl, holds, cuts, jolts, characters),
  `CONCEPT.md`, `lyric-options.yaml`, `lyrics.md`, `directions.yaml`, `LOOK.md`, `STORYBOARD.md`, `NOTES.md`,
  `JOURNAL.md`, `SOURCES.md`, `README.md`, `look.ts`, `video.ts`, `scenes.ts`, `cuts.ts`, `scenes/*.tsx`; `notes/`
  and `requests/` (written by the pages).
- Working files, in `<work>`: the song's copy, timings, vocals, previews, renders, checks. All regenerable; `clean`
  deletes them once the video is delivered. (Your hand-written corrections, `timing-fixes.yaml`,
  `lyrics-as-sung.txt` and `song-fixes.yaml`, are not working files: they live in `<video>`.)
- Finals, in `<results>`: the videos, thumbnail, subtitles, the song, and `<web>` (the live page). In a git
  worktree, the song stays in the main results folder, so `<results>` and the home's finals list hold only the
  video's own files.
- `<id>` is the song spec's id (the workspace's `specs/<id>.yaml`).

**Resuming:** read `video.yaml` (`step:`), `JOURNAL.md` and `NOTES.md`, and the video's open requests
(`requests <id>`); continue at that step. At every ✋, add a `JOURNAL.md` entry (date, what you showed, what the
user said, what is next) and update `step:` and the checklist, and write in `waiting:` what the user is asked for
now, in a few words ("pick a lyric", "notes on draft v2"); empty it once they have answered. The home shows it.

**Picture before the song** (a proof of concept, a look test, visuals the song comes after): give the video a
silent placeholder song instead of skipping the song's files by hand:

```bash
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" new-video <id> --placeholder <seconds>
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" placeholder <id> --seconds <s> --bpm <tempo>
```

It sets `placeholder:` in `video.yaml` and writes a silent song, no words and a steady beat grid with 8-bar parts
into `<public>`; render, stills, the board and `qc` work on it (qc skips the song's checks and says so). Render
`--muted` and run `qc` on the silent render (no `mux`). A placeholder render is never delivered or called final:
steps 3–4 still come before step 8, and filing the real song under the same id, then `align` and `analyze`,
replaces the placeholder (scenes then move onto the song's sections). A clip with no song and no placeholder at all
is checked with `qc --silent`.

## The home: the user's page for every video

`home` serves one local page with every song and video and its stage; each video opens on its ten stages, with what
is waiting for the user and links to its pages. In the project folder it serves on `http://127.0.0.1:8646/`; in a git
worktree of the project, on a free port. Its buttons never run anything: each one queues a **request** that you carry
out here. Start it in the background at the start of a session (it serves until stopped), with a wait for requests
beside it, also in the background, and give the user the address `home` prints: never 8646 from memory (in a
worktree, 8646 is the main checkout's home, whose requests belong to another session).

```bash
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" home --open
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" requests --wait
```

`requests --wait` returns as soon as a request is waiting (at once if one already is) and prints it. Then, and at
every ✋ and when resuming, list them, say in the chat what you picked up, and take each one (the page shows "Claude
is on it" with your message):

```bash
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" requests
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" requests --take <ref> --message "<what you are doing>"
```

A ref is `<id>:r<n>`, or `_home:r<n>` for the home's own queue. Carry the request out as the stage below says,
with `requests --update <ref> --message "…"` on long steps, then mark it done with what came of it, and start the
wait again:

```bash
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" requests --done <ref> --message "<what came of it>"
```

A request is the user's own words, typed on a page instead of the chat; every hard rule still holds, and a request
you cannot carry out is marked done with the reason. The kinds:

| kind | the user clicked | you do |
|---|---|---|
| `new-video` | New video, with a topic | step 1 from the topic, then step 2's options; `--done … --video <id>` |
| `pick-lyric` | Use this one, on a lyric option, with a note | step 2.2–2.4 with that option, merged as the note says |
| `lyrics-again` | Write new options, with a note | a new round of options (step 2.1) |
| `create-takes` | Send to the generator, with directions ticked | step 3.2 for those directions: this is the OK on them |
| `use-take` | Use this take (twice) | step 3.4 with that take: this is the user naming it |
| `approve` | Approve, on a stage, with a note | that stage's approval, as if typed, note and all |
| `variant` | Make a variant, on a section of the sections page | step 7.4's variant of that section |
| `clean` | Free the working files (twice) | step 10: `clean <id>` (the second click was the OK) |
| `message` | Tell Claude | read it as a chat message |

The home also starts the sections page and the timing editor of a video when the user opens them (inside the home,
on free ports); after a timing editor save, check the entries landed as step 4 says.

## 1. Concept ✋

Talk through: what the song is about, who it is for, the feeling, a genre direction, the language (default
English), the length (3–4 min). Propose one concept: a short paragraph plus the story arc (verse → pre-chorus →
chorus → bridge → final chorus). Wait for approval. Then make the video's folder, with an id from the subject
(lowercase words joined by hyphens, short: `paper-boats`), so the home can show it; the song's spec takes the same
id in step 2:

```bash
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" new-video <id>
```

Write the concept into `CONCEPT.md` and set `step: lyrics`.

**From a `new-video` request** (a topic typed on the home, maybe with a note): the user asked for lyrics from it.
Make the folder as above, write `topic:` (their words) in `video.yaml`, the concept you propose into `CONCEPT.md`,
and go straight on to step 2's options; picking a lyric approves the concept too (a note can redirect it). Mark the
request done with `--video <id>`.

## 2. Lyrics ✋

1. Write 2–3 complete options from different angles, following `references/lyric-craft.md`, into
   `<video>/lyric-options.yaml` (the home shows them side by side), and show them in chat too. Set
   `waiting: pick a lyric`. A new round (the user asked for other options) is added under `rounds:`, with the note it
   answers:

   ```yaml
   rounds:
     - n: 1
       at: 2026-11-05T09:12:00
       note: ""
       options:
         - key: A
           title: <title>
           angle: <the angle, in a few words>
           lyrics: |
             [Verse 1]
             …
   ```

2. The user picks, combines, adds lines (in the chat, or **Use this one** on the home with a note: "take the chorus
   from B"). Merge into one final version, write it under `final:` (`title`, `from`: what it was made from, `lyrics`)
   and show it with the title.
3. WebSearch `"<title>" song`; if a well-known song uses the title, propose another.
4. When approved, create the spec with the video's id (it prints the spec's path):

   ```bash
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" new --title "<title>" --id <id>
   ```

   - Put the lyrics into the spec's settings block (`lyrics` in the `suno:` block) and run `validate <id>`:

     ```bash
     uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" validate <id>
     ```

   - In `<video>/index.tsx` set `TITLE` to the song's title (it is printed on the thumbnail).
   - Write `lyrics.md` (the final lyrics first, then the options under "Options considered"); set `lang:` in
     `video.yaml`; `step: song`.

## 3. Song ✋

1. Write 2–3 musical directions into `<video>/directions.yaml`, a list, each a complete settings block for the
   generator (the `suno:` block, as its `workflow.md` says) built from the genre recipes, with a one-line `name` and
   `why`. Show them as a short table (the home shows them too, with a box to tick each); set
   `waiting: choose the directions`. On the user's OK they are created: in the chat, or a `create-takes` request,
   which names the directions to create (only those; its note may change them first).
2. For each direction: copy its block (with the lyrics) into the spec's `suno:`, run `validate <id>`, then run the
   song skill's steps 2 (Fill), 3 (Verify) and 4 (Create), recording the round with
   `--changes "direction <n>: <name>"`.
3. Show one table of every take (direction · take · length · link). The home lists them too, each with a link to
   it in the generator and **Use this take**. Set `waiting: pick a take`. The user listens and names one (in the
   chat, or a `use-take` request: that is naming it), or asks for another round (new or changed directions; repeat
   2).
4. Copy the chosen direction's block into the spec's `suno:` (so the spec describes the kept take), run
   `validate <id>`, then the song skill's step 6 (Download) and step 7 (Ingest). `step: timing`.

## 4. Timing ✋

1. Word timings (the first run on a machine installs the alignment models; give it time). A new take or a
   language change is detected automatically; `--force` redoes everything by hand. Then the song map and a
   karaoke preview. A video made from the template has `onsets: true` in `video.yaml`: `align` moves each word's
   start onto its first sound, measured on the vocals (an s on its hiss, a p on its burst, a vowel or an m on the
   voice; never a breath). Videos made before 0.8.3 have no such line and keep their timing; switch one on only when
   the user asks (`onsets: true` in its `video.yaml`).

   ```bash
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" align <id> --lang <lang>
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" analyze <id>
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" preview <id> --open
   ```

2. Show the user: the align summary (repairs, the onsets line, unsure words with times, possibly missing lines), the tempo and the
   sections (analyze's drums line too: where the hits were measured, and a beat grid more than 0.1 beat off the
   drums is checked on the preview's beat dots), and ask them to watch the preview. Its bottom panel shows the vocal waveform 10 s at a time with a
   moving playhead, 0.1 s ticks and a mark at each word's start: a word's true start is where the waveform rises
   after a dip, so a fix can be read off it to the tenth of a second.
   - Always offer the timing editor with the preview (users find dragging words easier than writing fixes): a
     local page where the user drags each word's mark onto the waveform or the spectrogram under it (a word's first
     sound shows best there: an s or f is a haze high up, a p, t or k a thin vertical line), plays the song around it,
     and saves (it
     writes the `timing-fixes.yaml` entries and re-runs align and analyze). Run it in the background and give the
     user its address (`http://127.0.0.1:8644/`); it keeps serving until stopped. After each save, check the
     entries landed and commit `timing-fixes.yaml`. Stop it when the timing is approved (it can be started again
     at any time):

     ```bash
     uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" edit-timing <id> --open
     ```

   - Bad words → write `<video>/timing-fixes.yaml` entries with the times read off the preview or the editor
     (`- at: "1:13"` / `word: thunder` / `start: 73.42`, and `end:` when it is wrong too), re-run align and preview.
     Never write `shift:`: it is added to the aligner's start, not to the start the preview shows.
   - A word sung one way but written another (a number sung as words: "nine-to-five" shown as "9-to-5") → a
     `timing-fixes.yaml` entry `- word: Nine-to-five` / `show: "9-to-5"` (every occurrence; add `at:` for one).
     Only the text in timing.json and the subtitles changes; the times stay. Re-run align and preview.
   - A line the generator did not sing (or sang differently) → write `<video>/lyrics-as-sung.txt` with the lyrics as sung
     (same tags), re-run align, analyze and preview.
   - A word that starts a second or more after the word before it in the same line is often aligned late (a word
     that is whispered, or that follows a held note, can land 1–3 s late). Listen at each one, and move it with a
     `start:` entry when it is wrong.
   - More than 10% unsure words → offer: fix words, use as-sung lyrics, or pick another take.
3. On approval: `step: look`.

## 5. Look ✋

Follow `references/look.md`: 2–3 directions, each a `LOOK.md` section and a look composition, 3–4 real 16:9
style frames plus one 9:16 chorus frame each, shown side by side on one sheet. Iterate until the user approves one
(or a merge).

With the directions, ask the **jolts** question, default no: "Should things jolt on the beat: the camera kicking on
the kick drum, a shake on the big hits?" It is this video's choice, not a rule either way. Record the answer (and
what jolts, when yes) as the **Jolts:** line of `LOOK.md`, as `jolts` in `look.ts` and as `jolts:` in `video.yaml`;
when the user does not answer, it is no. Every scene follows it (`references/studio.md`).

When the concept has characters, each direction also names its **character engine**, so the sheet compares
engines as well as styles: `raw` (you draw and move the characters from scratch in scene code; always offered,
first), `vrm` (three-vrm anime characters from `@mv/kit/three`, with the CC0 sample avatars) or `cartoon`
(hand-inked 2D rubber-hose characters from `@mv/kit/cartoon`: brush lines that boil, eye pops and jaw drops,
squash and stretch). When the user wants
to see the engines move before choosing, or cannot tell from stills, run a bake-off (`references/bakeoff.md`):
`bakeoff new <id>` puts one take per engine on the review page as variants of the scene `bakeoff`
(`version … --scene bakeoff --variant <engine>`), and `bakeoff record` keeps the verdict. Record the choice as the
**Characters:** line of `LOOK.md`, `characterEngine` in `look.ts` and `characters:` in `video.yaml`; no characters
leaves them none/null.

Model watch, only when the video has characters: run
`uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" bakeoff last --model <your model id>`. When it says to
offer, offer once, in one line, to run the benchmark bake-off on its own later (`references/bakeoff.md`); it must
never block the video. A no is recorded with `bakeoff record --model <your model id> --declined`.

Then: final `LOOK.md`, `look.ts` values, remove the losing look code (and the bake-off's takes, with
`bakeoff clear <id>`). `step: sample`.

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
   even though these are excerpts (qc shifts them into the clip). qc reads the rest on its own: scene changes
   (`analysis.json`), designed hard cuts inside a scene (list each `ease: 'cut'` key in `video.yaml` `cuts:`, song
   seconds), word starts and the jolts answer. Its flicker, pop, hard-cut and jitter lines name frames: step through
   each one; a designed effect gets a hold or a cut entry, anything else is a bug to fix.

   Keep the clean sample as the first version on the review page (it refuses a render that has not passed qc):

   ```bash
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" version <id> "<renders>/sample-clean.mp4" --scene sample --excerpt <from>-<to> --note "<what it shows>"
   ```

6. Show together: the storyboard (as text), the board panels, both samples. Ask the subtitles question with a
   default: none / whole lines / word highlight, and the style. On approval: set `subtitles` in `look.ts` and
   `video.yaml`; `step: production`.

## 7. Production ✋

1. For every storyboard section without real code, dispatch a scene agent with the brief template in
   `references/studio.md` (at most 4 at a time; they write only `scenes/<section>.tsx` and render stills only).
   Review each agent's stills yourself; re-brief any scene that drifts from `LOOK.md`. Keep the stills you show as
   versions of their scene (`version <id> <still.png> --scene <section> --at <song seconds>`), so the next pass of
   the scene can be compared with this one.
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

   Add `--hold a-b` to qc for every designed hold in `video.yaml`. Fix and re-render on any problem. Then keep it
   as a version (versions live in `<work>/review/`, so the render itself can be deleted once kept; the review page
   holds every earlier draft) and open the sections page on it:

   ```bash
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" version <id> "<renders>/draft-v<n>.mp4" --scene draft --note "Round <n-1>: <the notes it answers>"
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" sections <id> --open
   ```

   Keep every version the moment it passes qc, never batching or holding one back. Give it `--issue "<what is
   wrong, with its song time>"` for each thing you already know is wrong (qc flags you judged real, frames you
   still have to fix): the review page shows a version's known issues first. A kept version is marked waiting
   review (it replaces the mark of the scene's earlier version). When the user gives notes on it, mark it reviewed
   with their words, verbatim (reviewed is not approved):

   ```bash
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" review <id> --version draft:v<n> --reviewed "<their words>"
   ```

   The sections page lays the newest draft out by the scenes in `scenes.ts`: every section on one screen, each
   playable alone, in order (**Play the flow**) or with its neighbours' joins. Opening a section gives a large player
   with frame stepping, a filmstrip, and a notes panel: a note keeps the frame on screen (song time, frame number,
   which draft), and **Draw on frame** marks a full-size frame with a pen, arrow, box or circle. Run it in the
   background and give the user its address (`http://127.0.0.1:8645/`); it serves until stopped. Restart it on each
   new draft (it shows the newest one when it starts; `--video <file> --start <s>` shows another render).
4. Show the draft. When the user says their notes are in (or types more in the chat), read the page's notes:

   ```bash
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" notes <id>
   ```

   It prints each new note with its section, song time, frame and draft, and the paths of its frame image and of the
   frame with the user's drawing. Look at every drawn frame (and the frame of any note whose words point at
   something on screen) before answering; the drawing shows where, the words say what. Treat them exactly like
   notes typed in the chat. Write them into `NOTES.md` under "Round <n>" with their song times and image paths,
   together with any notes from the chat, then mark them taken (`notes <id> --taken <n>`); taken notes stay on the
   page, greyed, under their round. Number every note in the round and sort each into error or taste. The
   next version answers every note in `NOTES.md` (what changed, or why not; never just "addressed"). Changed
   sections can come back first as clips (`--frames=a-b`); a clip also goes through `mux --excerpt` and
   `qc --excerpt` before it is shown (hard rule 4), then `version <id> <clip> --scene <section> --excerpt <from>-<to>
   --note "<the notes it answers>"`. On the review page the user compares the new version with the last one (or
   with the draft, lined up on the song clock): side by side, a wipe, or flipping; **Copy timecode** gives them a
   line like `relay v3 vs relay v2 at 1:42.3` to quote in a note.

   **Variants.** For a risky section (a technique new to this video, the big moment: the drop, the last chorus),
   build two variants of the scene on your own; when the user asks for one (a `variant` request from **Make a
   variant** on the sections page, with what it should try), build it. Render each as a clip of its section, check
   it like any clip, and keep it as a named variant (`a`, `b`, or a word for the idea):

   ```bash
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" version <id> "<renders>/<section>-b.mp4" --scene <section> --excerpt <from>-<to> --variant b --note "<what it tries>"
   ```

   The user compares them on the sections page: in an opened section, **Compare** plays any two versions of it (the
   draft, an earlier draft, a clip, a variant) side by side, with a wipe, or flipping, on one clock, and a note can be
   on either side (its render says which, as `notes` prints it). The variant they pick goes into the next draft.

   For an error no check caught, propose a new entry for
   `references/checks.md`; for taste, a line for the workspace's `taste.md` (see `references/taste.md`); add them
   only with the user's OK.
   A word the take barely sings (the user cannot hear it): first measure it (`vocals.wav` and the mix around the
   word's time). If it sits 30 dB or more under its line in the vocal stem, the singer barely sang it: a lift makes
   it audible but never as clear as its neighbours, so say so up front (re-singing the window with the generator is
   a last resort; see its `controls.md`). Then offer lifts as an audio-only A/B test (the original, then each lift, from `ffmpeg`), and write
   the one the user picks into `<video>/song-fixes.yaml` (`- at: <s>` / `to: <s>` / `gain_db: 12` /
   `presence_db: 8` / `hiss_cut_hz: 6500` / `denoise: true`, see `music-video/scripts/musicvideo/video/songfix.py`).
   `mux` and `qc` then put the lifted song under the picture; timing and beats keep the original. A lift raises the
   band too: keep it to the word, and cut the hiss it raises (`hiss_cut_hz`).
5. Motion blur, when the look calls for it (smooth camera moves, fast objects): render with sub-frames and average
   them (32 samples, a 180° shutter). It costs about 30 s of render per second of 1080p video: a 4:40 video takes
   about 2 h 20 min, a 32 s vertical about 15 min. Show a 5–10 s camera move with and without it first (both as
   clips), then offer it for the final:

   ```bash
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" blur <id> <id>-full "<renders>/final-blur-silent.mp4" --samples=32
   ```

   `render` and `blur` kill a render that shows no progress for 15 minutes and start it again (twice at most;
   `--stall=<minutes>`, `--retries=<n>`). When the user asks
   how a long render is going, check that it is moving: the progress count in its output changes between two looks a
   minute apart, and the renderer is using the CPU (`ps`). A repeated last line is not progress.

6. On approval: `step: delivery`.

## 8. Delivery

Never deliver a video whose `video.yaml` still says `placeholder:` (qc fails a placeholder render in `<results>`):
file the song, `align` and `analyze` first.

Render, add the song, check, and render the thumbnail into `<results>`:

```bash
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" render <id> <id>-full "<renders>/final-silent.mp4" --muted --crf=18
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" mux "<renders>/final-silent.mp4" --spec <id> --out "<results>/<Title>.mp4"
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" qc "<results>/<Title>.mp4" --spec <id> --size 1920x1080
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" render <id> <id>-vertical "<renders>/vertical-silent.mp4" --muted --crf=18
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" mux "<renders>/vertical-silent.mp4" --spec <id> --excerpt <from>-<to> --out "<results>/<Title> (vertical).mp4"
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" qc "<results>/<Title> (vertical).mp4" --spec <id> --excerpt <from>-<to> --size 1080x1920
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" still <id> <id>-thumb "<results>/thumbnail.png" --frame=<the strongest frame>
```

(Use `final-blur-silent.mp4` from step 7 in place of the plain render when the final is motion-blurred.) Add the
same `--hold a-b` flags as the draft to the qc commands. Copy `<work>/lyrics.lrc`, `.srt` and `.vtt` to
`<results>/<Title>.lrc`, `.srt` and `.vtt` (players load them next to `<Title>.mp4`) and `<video>/README.md` to
`<results>/README.md`.

The thumbnail prints the title large in its lower left. Render two or three candidate frames (`still` into
`<renders>`) and look at them all. Pick the one where the title sits on a dark, plain area and covers no
character; then render it into `<results>`.

Look at both sheets and the thumbnail. Finish `README.md` and `SOURCES.md`. Open the deliverables for the user.
If the project folder is a git repository, commit the spec and `<video>` (never media). `step: done`. Uploading
is the user's. When they ask for a description to post with it, draft:
- a two-line hook in the song's voice;
- what it is about and how the lyrics appear;
- chapters from `STORYBOARD.md` (the first at 0:00, at least three, each at least 10 s long; most video sites
  turn these into a seekable timeline);
- how it was made (the song generator, the engine, no generated images if true) and the credits;
- a one-line caption for the vertical cut.

**YouTube end screen** (cards for other videos need 5–20 s at the end): when the song ends too soon after its last
picture, add a silent tail. Carry the last scene on past the song in its own composition (an `Excerpt` from the song's
end, 10 s; check the scene still moves sensibly there, and stop anything that follows the beat), render or blur it
like the final, then join it to the final's silent render by decoding both in order and encoding once at the
video's frame rate. Never join with `-c copy`: a stream-copy join starts the picture about 21 ms late and leaves
uneven frame timing that players show as repeated or dropped frames. Write `list.txt` with one `file '<path>'` line
per part (the final's silent render first, then the tail), and run
`ffmpeg -f concat -safe 0 -i list.txt -vf "setpts=N/(30*TB),setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv" -fps_mode cfr -r 30 -c:v libx264 -crf 18 -pix_fmt yuv420p "<renders>/final-tail-silent.mp4"`
(30 is the video's fps, 18 the final's CRF: match both; `setparams` keeps the BT.709 tags `qc` checks), then `mux ... --tail 10` and `qc ... --tail 10` on it. Keep the song-length final too: the tail is for YouTube only.

Point out the platform's AI-content disclosure (an AI-generated voice counts on most platforms).

The finished video and song also appear on the user's library page (any phone or TV at home): run
`uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" library` to print its address, or offer `library install`
(macOS) when it is not running yet.

## 9. Web page (optional) ✋

A live web page that draws the video in the browser, on a loop, from `<video>/web.tsx` (the template's plays the
whole video with its subtitles; a video can loop a stretch instead with the kit's `loopLayout` and keep only some
sung words with `words`). For sound, make a seamless loop of a song first (check the seam preview it prints):

```bash
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" loop <song id>
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" web <id> --audio-loop <song id> --title "<Title>" --description "<one sentence>" --label "<what it shows>" --background "#<page colour>"
```

The page lands in `<web>`, ready to copy to a website. Open `<web>/index.html` through a local web server (for
example `uv run python -m http.server -d "<web>"`) and check it in Chrome with the user: the loop wraps without a
jump, the sound button works. Copying it to a site is the user's call.

## 10. Clean up

Last, once the user is happy with the finals (and the web page, if any), offer to free the working files: renders
can be gigabytes, and the review page's versions go with them. The timing corrections stay in `<video>`; a later re-render re-runs `align` and `analyze` first.

```bash
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" clean <id>
```
