# Changelog

## 0.8.1

- The home shows a video's concept as formatted text instead of raw markdown.
- Videos made before the home show their final lyrics: when no option was picked on the home, the Lyrics stage
  shows the lyrics the song was made with, from its spec.

## 0.8.0

- `home`: one local page for every song and video. A card per video with its stage out of ten, what is waiting for
  you and the requests in flight; songs with no video; a **New video** form that takes a topic. Each video opens on
  its ten stages, each with its state and its pages: the karaoke preview (played in the page), the timing editor and
  the sections page (started from the home, on free ports), the look frames, the review page, the finals, the live
  page.
  - Lyrics side by side, from the new `lyric-options.yaml`: **Use this one**, with a note ("take the chorus from
    B"), or **Write new options**.
  - The song: the musical directions with a tick box each and **Send to Suno**; the takes with a link to each in
    Suno and **Use this take** (two clicks: it names the take, and only it is downloaded).
  - **Approve** on every stage you approve, with a note; **Tell Claude** for anything else; **Free the working
    files** at the end.
- Buttons queue requests, never run anything: one queue per video (`<video>/requests/`) and one for new videos. The
  page shows each request's progress (waiting for Claude, Claude is on it, done) and lets you cancel one Claude has
  not started.
- `requests`: what you asked for on the pages, for Claude to carry out; `--take`, `--update`, `--done` move a request
  along with a message the page shows; `--wait` returns as soon as one is waiting (Claude keeps it running in the
  background, so a click wakes it).
- Sections page: **Compare** (C) in an opened section plays it in two versions at once, on one clock (this draft, an
  earlier one, a clip, a variant): side by side, wipe or flip, frame by frame, sound from either; a note can go on
  either side and keeps that version's frame. **Make a variant** (V) asks Claude for a second version of the
  section.
- Sections page: quick presses of `.` and `,` always add up; a late report from an earlier seek could drop one.
- Two clicks at once on a page both reach the queue; one could write over the other.
- `version --variant <name>` keeps a render as a named variant of its scene (the review page shows it too).
- The make skill: the home and its requests; `waiting:` (what you are asked for now) and `topic:` in `video.yaml`;
  the video's folder is made once the concept is approved (the spec takes its id: `new --id`); lyric options on
  file; two variants of a risky scene. The song skill: a request on the home is your OK on the directions, or your
  pick of a take.

## 0.7.3

- Sections page: a tooltip shows once a page load (quickly, the first time you point at that kind of button); after
  that, only when the pointer rests on the button for 5 s.
- No more glimpse of the section played before: a player that jumps to another section stays hidden until the new
  frame is up (the card's picture, or black, shows meanwhile).
- A scene's note (from `scenes.ts`) is in italics, so it reads apart from the lyrics.
- `sections --video draft-v3.mp4` names the render "draft v3", as kept drafts are named.
- README: screenshots of the sections page and of a section opened, from a demo song.

## 0.7.2

- Sections page: each section keeps its place. Pause one, play another, and the first carries on where you left it
  (its card shows the paused frame meanwhile); opening it continues from there too. A section that played to its
  end, or that the flow ran past, starts over.
- Every button explains itself in a tooltip that shows a moment after you point at it (Play on, With neighbours,
  the drawing tools…).

## 0.7.1

- Deleting a note on the sections page removes only that note's own frame images (named by its id), whatever
  paths `notes.json` holds.

## 0.7.0

- `sections <id>`: a new page for watching a draft and giving notes, laid out by the scenes in `scenes.ts`.
  - Every section on one screen, in song order, under a strip that shows each to scale on the song. Each section
    plays alone; **Play the flow** runs them in order with one player, so the joins play as they will; **With
    neighbours** plays the end of the section before and the start of the next.
  - Opening a section gives a large player of the draft itself, with frame stepping, a filmstrip (a frame a second),
    its lyrics lighting up as sung, and its note from `scenes.ts`.
  - A notes panel beside it: typing pauses the video, and the note keeps the frame on screen (song time, frame number,
    which draft). **Draw on frame** grabs that frame at full size from the render, to mark with a pen, arrow, box or
    circle; the drawing is saved over the frame with the note.
  - Notes live in `<video>/notes/` (each with its frame as a JPEG, and the drawn frame).
- `notes <id>`: the new notes in song order, with section, song time, frame, draft and image paths, for Claude to read
  like notes typed in the chat; `--taken <round>` marks them as written into that round of `NOTES.md`.
- The make skill opens the sections page on each draft and reads its notes into the next round.

## 0.6.9

- A git checkout of the plugin (a clone or a worktree, for working on the plugin itself) uses its own engine in
  `engines/<checkout>/` under the install folder. Its packages are hard links to an installed engine with the same
  lock, so setting one up takes seconds and almost no disk. The installed plugin keeps `engine/` as before.
- Only one command at a time updates an engine (sync, packages): the others wait, with a message after two seconds.
  Renders still run side by side.
- A running command marks the engine as in use: another plugin version no longer syncs over it, and `doctor` no
  longer reinstalls its packages, mid-render. It says which version and video hold it instead.
- `web`: two builds at once, even of different videos, no longer swap song data (each build stages it in a folder
  of its own).

## 0.6.8

- `edit-timing`: a spectrogram under the waveform (on by default; the S key or its checkbox hides it), drawn from the
  mix or the vocals, whichever is shown. A word's first sound is easier to place on it than on the waveform: an s or f
  is a haze high up that can start several frames before the vowel, a p, t or k a thin vertical line, a vowel a stack
  of bright bands. Each word's mark runs through it and can be dragged there too. The page's help explains how to
  read it.

## 0.6.7

- `mux --tail <s>` and `qc --tail <s>`: a full video that runs on past the song, silent, for that many seconds (room
  for a YouTube end screen, 5–20 s). mux pads the song with silence; qc expects the longer video and audio.
- make skill, delivery: how to add an end-screen tail (the last scene carried on past the song, rendered or blurred
  like the rest, joined to the final).

## 0.6.6

- `blur`: a render that shows no new progress for 15 minutes (a hung browser, every process idle, which Remotion's
  per-frame timeout does not catch) is killed with everything it started and started again, up to twice; the pixels
  are the same as an uninterrupted render. `--stall=<minutes>` changes the limit (0 turns it off), `--retries=<n>` the
  number of restarts.
- make skill: when asked how a long render is going, check that its progress count moves and that it is using the CPU,
  not only its last line.

## 0.6.5

- make skill, timing step: the timing editor is offered with every preview (not only when many words are off), with
  its address; the skill commits the fixes after each save and stops the editor once the timing is approved.

## 0.6.4

- `edit-timing`: the status line (saving, saved, errors) is larger, white, and marked while work is under way; the
  help is two short tables (how to, keys) instead of a paragraph.

## 0.6.3

- `edit-timing`: the playhead and the highlighted word follow the sound as heard, not as handed to the audio device:
  they wait the output latency the browser reports, or what the *Audio delay* slider is set to (0–500 ms,
  remembered). Browsers do not see the delay of Bluetooth headphones and some speakers (about 150–250 ms), so set it
  by ear there.

## 0.6.2

- `edit-timing`: Stop answers every click while playing (the button, and the line's words, were rebuilt on every
  frame, which swallowed a click whose press and release fell on different frames). The labels inside the waveform
  sit on one line, each cut where the next word starts.

## 0.6.1

- `edit-timing`: Play/Stop is the large bright button (with an icon for each state), set apart from its neighbours;
  ⏮ Line start (`B`) replaces −5 s/+3 s and goes back to the first word of the line (again: the line before). Moving
  a word's start now carries the whole word: it keeps its length and only shortens against the next word (the word
  before gets its end back when a drag returns). The word being sung is highlighted in the line (the last word
  started, so gaps between words keep it lit) and shown alone under the waveform, speed-reader style; every word's
  label is also drawn inside the waveform. The waveform shows the source being heard (mix or vocals), and *Colour by
  frequency* (`F`) colours it by its spectral centroid, so vowels and consonants stand apart. A legend explains the
  colours; the source and the colour choice are remembered.
- `edit-timing` and timing fixes: a word exactly 0.06 s long is no longer refused as too short (floating-point
  rounding); the editor writes `at:` and its messages as m:ss.mmm.

## 0.6.0

- `edit-timing <id> [--open]`: a local page (this computer only) for fixing word timings by hand. It shows the song
  10 s at a time like the preview's panel (the vocal waveform with its loudness, 0.1 s ticks, beat dots and a mark
  at each word's start); drag a word's mark to where it is sung, or the handle at the end of its bar to move its end.
  ▶ −5 s/+3 s plays around the cursor, from the mix or the vocals alone; arrows nudge by 10 ms; ⌘Z undoes. Saving
  appends one `timing-fixes.yaml` entry per moved word (hand-written entries and comments stay), re-runs align and
  analyze, and names any word that did not land where it was put; if align refuses, the file is put back.

## 0.5.5

- `preview`: the vocal waveform is drawn 10 s at a time with a moving playhead, 0.1 s ticks, a label at every
  second and a mark with the word at each word's start, plus a clock to the millisecond, so a word's start can be
  read against the voice (the old strip scrolled past the playhead and showed only the current instant).

## 0.5.4

- Security: the studio's locked dependencies move past open advisories. `zod` 4.5.4 -> 4.6.7 (high; Remotion still
  pins 4.5.4, so an override forces it), vitest 3 -> 4.1.12, which drops `tinypool` (critical) for good, and
  `@vitest/mocker` 4.1.12 (medium). `doctor` installs them on the next run.

## 0.5.3

- `blur --scale=<n>` renders at that multiple of the composition's size, like `render --scale` (a 4K cut of a
  1080p composition).

## 0.5.2

- `library install` over a running copy waits for it to stop before starting the new one (launchd refused the
  start with "Input/output error" and left the library stopped).

## 0.5.1

- `library` answers only requests addressed to this computer by an IP address, `localhost`, a `.local` name or its
  own name, and refuses any other host name: a website whose domain was pointed at the computer (DNS rebinding)
  can no longer read the library through a browser on the home network. Run `library install` again to refresh a
  running copy.

## 0.5.0

- `library`: everything in the results folder (videos, songs, lesson units, albums) as one page that any phone,
  tablet or TV browser on the home network can play from: newest project first, titled from its README, thumbnails
  (a poster frame when there is none), subtitles from a `.vtt` beside the video, a Loop button and Play all, songs
  in the page, live web pages linked. Videos are served in byte ranges, so phones seek and AirPlay works. Folders
  starting with `_` or `.` (paid source media, working files) are never listed or served. `library install` keeps
  it running from login on macOS (a launchd agent running a copy in the install folder); `library serve` runs it
  in the foreground on any platform; `library uninstall` removes the agent.

## 0.4.1

- Python is capped below 3.15: PyYAML has no 3.15 wheels yet, so a fresh install picked 3.15 and tried to compile
  it, which fails on Windows (it needs Microsoft C++ Build Tools) and on a Mac without Xcode's command line tools.

## 0.4.0

- `qc` has a `flash` check: a run of 1–6 frames far darker (or brighter) than the frames on both sides of it fails,
  so a scene captured before it finished loading no longer slips through. Such frames are dark but not true black,
  which the `black` check (3 frames of true black) misses. A cut (a step) and a fade pass. It adds about 10 s to a
  4-minute video.
- The 3D kit has lyric surfaces (`surfaceTexture`, a canvas texture redrawn only when what it shows changes, with
  `sungWords`, `wrap`, `bareEnd`, `paperGrain`). `useFontsReady` holds the render until a scene's web fonts can be
  drawn and the scene has drawn once with them; that fixes blank frames where a scene mounts at a cut.
- The 3D kit has a finishing pass:
  - `FinishPost`, a film-print post (halation-tinted bloom after the sanitize pass, print contrast and shoulder,
    warm or cool toe, vignette, clumped grain, soft corners with a faint fringe), with `FINISH_DEFAULTS`;
  - depth for flat things: `cardGeometry` (paper with thickness and a lifted corner), `SoftShadow`, `Thumbtack`,
    `Screw`, `wavyPlane`;
  - carved mitred frames: `frameGeometry`, `arcPts`, `mouldingWoodTex`, `mouldingBumpTex`;
  - `bevelBox`, and relief maps through `setRelief` and `reliefParams`.
- The make skill and its references:
  - new error checks: `flash`, `lyric-early`, `framing`, `flicker`, `buried`, `left-behind`, `word-late`;
  - studio rules: small, eased beat motion; characters framed whole; never two faces in one plane; characters
    stood on the floor by their lowest point; distant lights fading out; agents delete nothing;
  - a **Finish** line in the look;
  - the vertical cut ends on a finished thought;
  - late words after a pause at timing;
  - when a quiet word cannot be saved;
  - the cost of motion blur (about 30 s per second of 1080p video);
  - thumbnail candidates;
  - a description to post with the video.
- The Suno controls reference covers Replace Section: its limits, and why a mix lift comes first.

## 0.3.2

- The camera follows a monotone cubic curve through its keys (Fritsch–Carlson) instead of a centripetal Catmull-Rom:
  it still passes every key, but it never overshoots one or runs backwards between two on any axis, and a held aim
  stays still. Catmull-Rom looped where keys were dense or held, which showed as a small backward jolt as the
  camera left or reached a framing. Every key, and so every framing, is unchanged.

## 0.3.1

- `<video>/song-fixes.yaml` lifts a word the take barely sings: a fader ride over the stretch (`gain_db`, up to
  18), with an optional presence boost (`presence_db` at `presence_hz`), a cut above the voice so the raised hiss
  stays at the song's own level (`hiss_cut_hz`), a spectral denoiser (`denoise`), and fades in and out. `mux` and
  `qc` use the lifted song (built once into `<work>/public/song-lifted.wav`, rebuilt when the fixes or the song
  change); alignment, beats and the vocal stem keep the original.
- The make skill measures a quiet word first, offers lifts as an audio-only A/B test, and records the user's pick.

## 0.3.0

- `version <id> <file> --scene <name>` keeps a render (or a still) as the next numbered version of a scene, in
  `<work>/review/`, with the song time it starts at (`--excerpt`, `--at`), a note, and the video code's commit. A
  render must have passed `qc`, and not changed since, before it is kept.
- `review <id> [--open]` writes the review page: every version by scene, and any two played in sync on the song
  clock (so a scene clip lines up with a full draft), side by side, with a wipe, or flipping between them; frame
  steps, half speed, sound from either side, and **Copy timecode** for quoting a moment in a note.
- The make skill keeps the sample, the stills shown in production, each draft and each changed-section clip as
  versions, and opens the review page with every draft, so earlier drafts stay comparable instead of being
  deleted.

## 0.2.2

- `web` no longer refuses valid ways of exporting `web` (`export * from …`, `export async function web`,
  `export class web`, `export { w as web }`); a `web.tsx` without a usable `web` export (renamed, deleted, or not
  `{ Component, fps, frames }`) is named by the build in one line.
- A folder whose README is not text is refused as "not a web build" in one line (it gave a traceback).
- `ingest --file` decides by where the file sits, not where a link points: a link you made outside the downloads
  folder is kept.
- An album `cover:` that is not a file name is a named error.
- Tests: the web build's marker is checked to match on both sides; the UTF-8 check also covers `open`,
  `Path.open`, `Popen` and `check_output`, and the engine's Python tools; the privacy scan is checked to cover the
  plugin's own code, skills and engine.

## 0.2.1

- `web` refuses a non-empty folder that is not its own build, a file as `--out`, or a `web.tsx` without a `web`
  export, in one line, before building anything.
- Albums are checked strictly: an unknown album id, `styles:` that is not a mapping, a missing cover, and a song
  whose style left the album are all named errors; `album <typo>` no longer writes an empty manifest.
- The default results folder follows the platform (`~/Movies` on macOS, `~/Videos` elsewhere); on macOS the
  settings file now lives in `~/Library/Preferences/music-video/` (copied there for you), apart from the install
  folder.
- Sung words are matched the same way everywhere (scenes' `findWord`/`findLine` and a web page's `words`): every
  script, Latin accents ignored, the marks that change a word elsewhere kept.
- `ingest --file` keeps a file you point at outside the downloads folder (downloads are still tidied away).
- Remotion, tsx and tsc run through node and their own entry scripts (no npx shim re-parsing arguments on Windows;
  `doctor` installs the build tools even where npm is set to skip dev dependencies);
  every text read and write names UTF-8; the skills give only the plugin's own commands.

## 0.2.0

- Four folders: project (specs, albums, video code), install (the engine and models, once), work (regenerable
  files; `clean <id>`) and results (finals). Upgrading moves the 0.1.0 engine instead of reinstalling it.
- Song generators: a spec names its generator (`generator: suno`); generator-specific guidance lives under
  `skills/song/references/generators/`.
- Albums: `albums/<album>.yaml` (title, year, cover, an artist and album name per style), filed into
  `results/albums/<album>/` with a `manifest.json`; `album <album>` rebuilds it.
- `loop <song>`: a seamless audio loop of a song. `web <id>`: a live web page of a video, looping, with optional
  sound; videos opt in with `web.tsx` (the template has one).
- The 3D typeface covers accented capitals; the CLI never writes into the plugin folder.
- Upgrading from 0.1.0: `doctor` moves the engine for you. Your `media_dir` is read as `results_dir`, but working
  files now go to the OS cache: move each `media/<id>/public/` (timings) into the work folder that `paths <id>`
  prints, or re-run `align` and `analyze`; move `timing-fixes.yaml` and `lyrics-as-sung.txt` into the video's
  folder; finals stay where they are.

## 0.1.0 — first release

- `make`: theme → lyrics → Suno song → timings → look → storyboard → rendered video, with an approval at every stage.
- `song` and `ingest`: Suno's Create form filled and verified in your own Chrome; downloads only the named take,
  counted against your plan.
- Word timings (vocal separation + alignment, repaired), song map, karaoke preview, and render checks (`qc`).
- A Remotion engine with a 2D kit, a 3D kit (camera rigs on the song clock, 3D lyrics, CC0 models), vendored MIT
  transitions, a transition board and motion blur.
- A per-user workspace outside the plugin; the engine installs once into the OS cache folder.
