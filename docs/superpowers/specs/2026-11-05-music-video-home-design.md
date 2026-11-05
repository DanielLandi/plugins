# music-video — the home: one page that drives a video from topic to delivery

**Date:** 2026-11-05 · **Status:** draft design, built on branch `music-video/home` (draft PR), awaiting review
**Scope:** `music-video` only: a new `home` command and page, a request queue (`requests` command), lyric options as
a file, a Compare control and a "Make a variant" button on the sections page, `version --variant`, the `make` and
`song` skills, README, CHANGELOG, version 0.8.0. `lesson-videos` is not touched.

## 1. Intent

The user, in their words: "A landing page that we can control everything from. We would start with writing the
lyrics given a topic and generating multiple variants. Then, from there, we select a lyric and you send it to Suno.
After we select the music there, you download and start working on the words alignment and storyboard." The A/B
review page should become useful, "especially if we create two variants to compare", and sit with the other
screens.

Today every decision is typed in the chat, and the pages (timing editor, karaoke preview, review, sections) are
separate commands on separate ports that Claude has to start. The home is one local page that shows every song and
video with its stage, opens each video's ten stages, and turns the user's decisions into **requests** that Claude
carries out in the CLI.

## 2. Decisions (the user's, 2026-11-04)

1. **Buttons queue requests.** A button records a request; Claude in the CLI picks it up and carries it out; the
   page shows its progress. The page never runs Claude. (Same pattern as notes on the sections page.)
2. **One home for everything.** A list of every song and video with its stage; click one for its own view of the
   ten stages. A **New video** form takes a topic and queues "start a video on this topic".
3. **Lyrics: pick + note.** The options side by side; the user picks one and may add a note ("take the chorus from
   B"); Claude merges.
4. **A/B compare lives in the sections page.** In an opened section, **Compare** plays that section in two versions
   or variants (side by side, wipe, flip, as the review page does), and notes can be left on either side. The
   standalone `review` page stays as it is (it is linked from the home).
5. **Variants:** Claude builds two variants of a risky scene (a new technique, a big moment) on its own, or when the
   user asks (**Make a variant** on a section queues it). Compare is how the user picks.
6. **Takes:** the page lists the takes with a link to each in the generator; the user listens there and clicks
   **Use this take**, which queues the download. That click is the user naming the take (song skill hard rule 1);
   the download is still recorded against the plan's downloads first.
7. **All ten stages** are shown, each with its state, what is waiting for the user, and links to its pages
   (karaoke preview, timing editor, look frames, sections page, compare, deliverables).
8. Deliver as far as possible: this design, a plan, the build with tests.

## 3. Limits

- The page never runs Claude, never drives the song generator and never spends credits or downloads: it only
  writes requests. Every hard rule of the make and song skills holds unchanged; a request is an instruction typed
  by the user, nothing more (a request to create takes is the user's OK on the directions; Use this take is naming
  the take).
- Local only: every server binds 127.0.0.1 and refuses other Host/Origin headers (`trusted_host`), as the
  sections page does. Bodies are size-capped; every request kind and field is validated; files are served only from
  named folders of that video, by pattern, never by a path from the client.
- No new dependencies. Python standard library + PyYAML (already used). One HTML file, no build step.
- Windows and macOS: `encoding="utf-8"` everywhere, argument-list subprocesses, no bash-only syntax in the skills.

## 4. Data

### 4.1 What the home reads (all exist today)

| What | Where |
|---|---|
| videos | every folder in `videos_dir` with a `video.yaml` (`step:`, `lang:`, checklist) |
| songs without a video | every spec in `specs/` whose id has no video folder |
| title | the spec's `title`, else the video id |
| takes | the spec's `rounds[]` (`changes`, `suno_urls`) and `kept.take_url` / `status` |
| downloads left | `budget.downloads_in_cycle` + `config.yaml` |
| directions | `<video>/directions.yaml` |
| karaoke preview | `<work>/preview.mp4` |
| look frames | `<work>/renders/frames/<letter>/*-sheet.png` |
| drafts and versions | `<work>/review/versions.json` (+ the review page `<work>/review/index.html`) |
| notes | `<video>/notes/notes.json` |
| deliverables | top-level files of `<results>` (videos, thumbnail, subtitles, the song), `<results>/web/` |

### 4.2 New files

**`<video>/video.yaml`** gains two optional keys, written by Claude:

```yaml
topic: "a night drive through a city that never sleeps"   # set when the video came from the home
waiting: "pick a lyric (or ask for new options)"           # what the user is asked for now; empty when nothing
```

`step:` keeps its values (`concept … delivery, done`); stages 9 (web page) and 10 (clean up) are read from the
files: a `<results>/web/index.html` means the web page exists; a missing work folder after `done` means cleaned.

**`<video>/lyric-options.yaml`**, written by Claude at stage 2 (replaces options shown only in the chat):

```yaml
rounds:
  - n: 1
    at: 2026-11-05T09:12:00
    note: ""                      # the user's note this round answers (empty for the first)
    options:
      - key: A
        title: Night Drive
        angle: the drive as an escape
        lyrics: |
          [Verse 1]
          ...
final:                            # once the user picked: the merged lyrics Claude goes on with
  title: Night Drive
  from: "B, with the chorus of A"
  lyrics: |
    ...
```

**Requests.** One queue per video, `<video>/requests/requests.json`, and one for the home,
`<project>/requests/requests.json` (new videos). A request:

```json
{"id": "r3", "n": 3, "at": "2026-11-05T09:30:12", "kind": "pick-lyric",
 "data": {"option": "B", "round": 1, "note": "take the chorus from A"},
 "text": "Use lyric B (round 1): take the chorus from A",
 "state": "new", "taken_at": null, "done_at": null, "message": "", "video": null}
```

States: `new` (waiting for Claude; the user can cancel it) → `taken` (Claude is on it; `message` is its latest
progress line) → `done` (`message` says what came of it; for a new video, `video` names the folder made). A
cancelled request is removed. Ids are never reused. A request is addressed in the CLI as `<video>:<id>`, the home's
queue as `_home:<id>` (`_` cannot start a video id).

| kind | from | data | Claude does |
|---|---|---|---|
| `new-video` | home form | `topic`, `note` | picks an id from the topic, `new-video <id>`, writes `topic:`, the concept and the lyric options |
| `pick-lyric` | lyric option | `round`, `option`, `note` | merges as the note says, writes `final`, goes on to the song stage |
| `lyrics-again` | lyrics stage | `note` | writes a new round of options |
| `create-takes` | directions | `directions` (numbers), `note` | the song skill's Fill/Verify/Create for those directions |
| `use-take` | a take | `url`, `round`, `note` | the song skill's Download (recorded first) and Ingest, then timing |
| `approve` | any ✋ stage | `stage`, `note` | the stage's approval, as if typed |
| `variant` | sections page | `section`, `note` | a second version of the scene, kept with `--variant` |
| `clean` | stage 10 | — | offers `clean <id>` (asks as the skill says) |
| `message` | any video | `note` | reads it as a chat message |

## 5. The pages

### 5.1 The home (`music-video home [--port 8646] [--open]`)

- **List:** a card per video and song: title, id, stage (n · name, with a ten-segment bar), what is waiting for
  the user, new requests in flight, new notes; queued new videos (topic, request state) on top.
- **New video:** a topic and an optional note → `new-video` in the home queue.
- **A video** (`#/v/<id>`): the ten stages down the left (done / now / waiting for you / later), the current stage
  open on the right; any stage can be opened. Each stage shows what it has:
  1. Concept: `CONCEPT.md`, the topic. 2. Lyrics: the options side by side (newest round), **Use this one** with a
  note, **New options** with a note; the final lyrics once picked. 3. Song: the directions with checkboxes and
  **Send to the generator**; the takes (round · direction · link that opens it in the generator) with **Use this
  take**; the kept take; downloads left. 4. Timing: karaoke preview (played in the page), **Open the timing
  editor**. 5. Look: the look sheets. 6. Sample: sample versions, the review page. 7. Production: **Open the
  sections page** (notes, Compare, variants), the review page, new notes, drafts kept. 8. Delivery: the finals.
  9. Web page: the live page. 10. Clean up: **Free the working files**.
  Every ✋ stage has **Approve** (with an optional note); every video has **Tell Claude** (a free note), and the
  list of its requests with their progress. The page polls the state every 2 s.
- **Opening the sections page or the timing editor** from the home starts it inside the home process on a free port
  (never 8644/8645, so a page Claude already started keeps running), once per video, and opens it in a new tab.
  These are the existing pages, unchanged apart from §5.2.

### 5.2 The sections page

- **⇆ Compare** (key C) in an opened section: two panes of that section, A and B, each chosen from the draft on the
  page and every kept version covering the section (earlier drafts, scene clips, variants), with Side by side /
  Wipe / Flip, one song clock, frame stepping, sound from A or B (the review page's logic). Default: A = the draft,
  B = the newest variant or version of this scene, else the draft before.
- **Notes on either side:** in Compare the composer says which side the note is on; the note keeps that version's
  frame (its label, e.g. `roof v4 (variant b)`, is the note's render), so `notes <id>` tells Claude which one.
- **⧉ Make a variant** in an opened section: a note box → a `variant` request in the video's queue; the page lists
  the section's variant requests and their progress.
- `version <id> <file> --scene <s> --variant <label>` keeps a version as a named variant.

### 5.3 The review page

Unchanged, linked from the home (stage 6 and 7). The Compare control covers the variant case inside the sections
page.

## 6. Request lifecycle in the CLI

```text
music-video requests [<video>] [--all] [--json]          # new and in-progress requests, oldest first
music-video requests --take <ref> [--message "…"]          # Claude starts on it (the page shows "Claude is on it")
music-video requests --update <ref> --message "…"         # a progress line
music-video requests --done <ref> [--message "…"] [--video <id>]
music-video requests --wait [--timeout <s>]                # returns when a new request arrives (run in background)
```

The make skill keeps `requests --wait` running in the background while a home is open: when it returns (Claude Code
wakes on a background command's end), Claude lists the new requests, says in the chat what it picked up, takes each
one, does it as the stage says, marks it done, and starts the wait again. It also checks `requests <id>` at every ✋
and when resuming.

## 7. What changes in the skills

- **make:** a Home section (open it, keep the wait running, how each kind maps onto the stages); at every ✋ write
  `waiting:` in `video.yaml` and clear it after; stage 1 from a `new-video` request (the topic; make the video folder
  first, with a working id; `new --id` later); stage 2 writes `lyric-options.yaml` and `final`; stage 3 directions →
  `create-takes`, takes → `use-take`; stage 7 variants on risky scenes, `version --variant`, Compare.
- **song:** a request to use a take is the user naming it; a `create-takes` request is the OK on the directions.

## 8. Tests

Unit: request store (add/validate/cancel/take/update/done, ids never reused, refs, `--wait`), project listing
(stages, waiting, songs without videos, queued topics), lyric options parsing, takes from rounds, file routes refuse
traversal and other hosts, sections versions/variant/notes-on-a-version. Browser (Playwright, like the sections
tests): the home lists demo videos, a new video request, pick a lyric with a note, use a take, approve; the sections
Compare shows two panes and saves a note on B; Make a variant queues a request. The demo data is generated (no
personal names), and the README screenshots come from it.
