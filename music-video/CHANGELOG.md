# Changelog

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
