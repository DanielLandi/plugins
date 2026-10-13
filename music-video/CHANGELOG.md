# Changelog

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
