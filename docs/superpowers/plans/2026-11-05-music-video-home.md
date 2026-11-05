# music-video home — implementation plan

Design: [`../specs/2026-11-05-music-video-home-design.md`](../specs/2026-11-05-music-video-home-design.md).
Branch `music-video/home`, worktree `~/Projects/.worktrees/plugins/music-video-home`. Commit and push after each task;
the gate is `MV_PUBLISH=1 uv run pytest -q` (needs the local `.private-terms.txt`). Draft PR only, no merge.

## Task 1 — request queue (`musicvideo/requests.py`, `requests` command)

- `Requests(folder)`: `all()`, `add(kind, data)` (validates kind and fields, builds `text`), `cancel(id)` (only
  `new`), `take(id, message)`, `update(id, message)`, `done(id, message, video)`; a lock and atomic writes like
  `Notes`. Ids `r<n>`, never reused.
- `queue_for(ws, video_or_None)`, `parse_ref("<video>:r3" | "_home:r1")`, `pending(ws)` across every queue,
  `describe(requests)` for Claude.
- CLI `requests [<video>] [--all] [--json] [--take|--update|--done REF] [--message] [--video] [--wait] [--timeout]`.
- Tests `tests/test_mv_requests.py`: lifecycle, validation, refs, cross-queue listing, `--wait` returns on a new
  request and times out.

## Task 2 — project reading (`musicvideo/home.py`)

- `projects(ws)`: videos (video.yaml), songs without video, queued `new-video` requests; for each: title, stage
  index 1–10, stage name, waiting, counts (new requests, new notes), updated time.
- `video_detail(ws, id)`: ten stages with state and links, concept text, lyric options (+ final), directions, takes
  (rounds → rows, kept), downloads left, preview, look sheets, versions, notes count, finals, web, work folder.
- `read_lyric_options(path)`: lenient parse with an `error` field when malformed.
- Tests in `tests/test_mv_home.py` with a generated demo workspace (`tests/mv_home_demo.py`, also used for the
  README screenshots).

## Task 3 — the home server and page (`musicvideo/video/home.html`, `home` command)

- Routes: `/`, `/api/state`, `/api/video/<id>`, `POST /api/request` (add/cancel), `POST /api/open` (sections or
  timing, started in-process on port 0, cached per video), `/v/<id>/preview.mp4`, `/v/<id>/look/<letter>/<sheet>`,
  `/v/<id>/review/…` (index.html + media), `/v/<id>/results/<file>`, `/v/<id>/web/…`. Host/Origin checks, body cap,
  ranges for video.
- Page: list + New video form; video view with the ten stages; lyrics side by side with pick+note; directions +
  Send; takes + Use this take; Approve + note; Tell Claude; requests with progress; polling.
- Tests: routes and refusals (urllib); Playwright: list, new video, pick a lyric with a note, use a take, approve.

## Task 4 — sections page: Compare, notes on a version, Make a variant

- `version --variant <label>` (stored on the entry; `name` shows it).
- `Sections.state()` adds `versions` (kept versions covering any section, with served URLs) and `requests`
  (variant requests). Routes `/versions/<file>`, `POST /api/request` (variant only).
- `Notes.add` accepts `version` (a kept version's file name): song time and frame grab from that version.
- Page: Compare panel (A/B pickers, side/wipe/flip, one clock, frame step, sound A/B, notes on A or B), Make a
  variant (note → request, list with progress).
- Tests: state carries versions; a note on a version; a variant request; Playwright compare + note on B.

## Task 5 — skills, README, CHANGELOG, version 0.8.0, screenshots

- make skill: Home section; `waiting:`; stage 1–3 from requests; `lyric-options.yaml`; variants in production.
  song skill: requests name a take / OK directions. Template `video.yaml`: `topic`, `waiting`, comments.
- README: How it works mentions the home; a "The home" section with screenshots made from the demo; Commands table
  (`home`, `requests`). CHANGELOG 0.8.0. Version bump in the three files and `tests/test_mv_packaging.py`.
- Gate, push, draft PR.
