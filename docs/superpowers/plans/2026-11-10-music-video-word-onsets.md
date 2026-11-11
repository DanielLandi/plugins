# Word starts on the first sound — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `align` moves each word's start onto the measured first sound of the word (hiss, burst or voice), for videos
that have `onsets: true` in `video.yaml` (every new video), and records how each start was decided.

**Architecture:** A new pure-numpy module `music-video/scripts/musicvideo/video/onsets.py` holds the spelling →
sound-class tables, the per-word measurement on the vocal stem, and `refine_onsets`. `align.py` calls it between
`snap_to_voice` and `apply_fixes`, skipping words a timing fix touches, when the video's setting (or a CLI override)
says so. `timing.json` words gain optional `sound`, `onset_conf`, `moved`; the timing editor shows the class.

**Tech Stack:** Python 3 + numpy (no scipy/librosa in the plugin), ffmpeg via `media.decode_mono`, pytest; the editor
is plain JS on a canvas.

**Spec:** `docs/superpowers/specs/2026-11-10-music-video-word-onsets-design.md`

## Global Constraints

- Windows and macOS; `encoding="utf-8"` on every file read/write; subprocesses as argument lists.
- No new plugin dependency: numpy only (`scipy` is test-env only, never import it from `musicvideo`).
- Nothing personal in the plugin or its tests (`tests/test_mv_privacy.py`); synthetic audio only in tests.
- `timing.json` stays `version: 1`; the new word keys are optional.
- Manual fixes win: a word any `shift`/`start`/`end` fix touches is never refined. `show:`-only fixes don't count.
- Off unless switched on: missing `video.yaml` or missing `onsets` key → off. Nothing rewrites existing `video.yaml`.
- Values from the spec: search window `start − 0.30 s` … `start + 0.25 s`; 5 ms hop; two windows (20 ms and 40 ms)
  must agree within 25 ms; move threshold `onset_conf ≥ 0.5`; vocals decoded at 44 100 Hz mono for onsets; fricative
  band 4–12 kHz; voiced band 100–1500 Hz; fricative must stay up ≥ 30 ms.
- Version bump (last task): `music-video/.claude-plugin/plugin.json`, its `.claude-plugin/marketplace.json` entry and
  `music-video/scripts/musicvideo/__init__.py` all `0.8.3` (`tests/test_mv_packaging.py`).
- The gate: `uv run pytest -q`.

## Review Focus

1. **Words that don't start with a letter** ("'cause", "9-to-5", "(oh)", "¿") — class comes from the first letter after
   stripping non-letters; a word with no letter is `voiced`. Test in Task 1.
2. **The first and last words of the song** — no previous word: the window starts at `max(0, start − 0.30)`; a start
   never goes below 0. Test in Task 3.
3. **A window with no clear event** (silence, a held note running through, steady noise) — the word keeps its start and
   `moved` is 0. Test in Task 2 and Task 3.
4. **Portuguese accents and ç** — `é`, `á`, `ó` fold to vowels (voiced); `ç` is a fricative; `Chão` is a fricative.
   Test in Task 1.
5. **A word whose move would squeeze the previous word under `MIN_WORD_S`** — the start doesn't move. Test in Task 3.

---

### Task 1: The first sound from the spelling

**Files:**
- Create: `music-video/scripts/musicvideo/video/onsets.py`
- Test: `tests/test_mv_video_onsets.py`

**Interfaces:**
- Produces: `Sound = Literal["fricative", "stop", "voiced"]`; `first_sound(word: str, lang: str) -> Sound`.

- [ ] **Step 1: Write the failing tests** — `test_first_sound_english`, `test_first_sound_portuguese`,
  `test_first_sound_odd_words`:

```python
@pytest.mark.parametrize("word,kind", [
    ("sunlight", "fricative"), ("shine", "fricative"), ("Charlie", "fricative"), ("photo", "fricative"),
    ("the", "fricative"), ("very", "fricative"), ("zero", "fricative"), ("city", "fricative"), ("gentle", "fricative"),
    ("jump", "fricative"), ("xylophone", "fricative"),
    ("paper", "stop"), ("better", "stop"), ("time", "stop"), ("door", "stop"), ("kite", "stop"), ("car", "stop"),
    ("queen", "stop"), ("go", "stop"),
    ("moon", "voiced"), ("night", "voiced"), ("love", "voiced"), ("road", "voiced"), ("we", "voiced"),
    ("you", "voiced"), ("open", "voiced"), ("home", "voiced"),
])
def test_first_sound_english(word, kind):
    assert first_sound(word, "en") == kind

@pytest.mark.parametrize("word,kind", [
    ("saudade", "fricative"), ("Chão", "fricative"), ("céu", "fricative"), ("cinema", "fricative"),
    ("ça", "fricative"), ("rua", "fricative"), ("Rosa", "fricative"), ("gente", "fricative"), ("janela", "fricative"),
    ("casa", "stop"), ("gato", "stop"), ("quero", "stop"), ("pão", "stop"),
    ("mar", "voiced"), ("noite", "voiced"), ("lua", "voiced"), ("hoje", "voiced"), ("é", "voiced"),
    ("água", "voiced"), ("ontem", "voiced"),
])
def test_first_sound_portuguese(word, kind):
    assert first_sound(word, "pt") == kind

@pytest.mark.parametrize("word,lang,kind", [
    ("'cause", "en", "stop"), ("(oh)", "en", "voiced"), ("9-to-5", "en", "voiced"), ("¿sí", "es", "fricative"),
    ("Tag", "de", "stop"), ("Mond", "de", "voiced"), ("", "en", "voiced"),
])
def test_first_sound_odd_words(word, lang, kind):
    assert first_sound(word, lang) == kind
```

- [ ] **Step 2: Run them to make sure they fail**
  Run: `uv run pytest tests/test_mv_video_onsets.py -q` — Expected: FAIL (`ModuleNotFoundError: musicvideo.video.onsets`).

- [ ] **Step 3: Implement `first_sound(word: str, lang: str) -> Sound`** in `onsets.py`, from the spec's tables
  ("The first sound"). Lowercase; detect `ç` before folding accents (`unicodedata` NFKD, drop combining marks); strip
  leading non-letters; no letter → `voiced`. `lang` is matched on its first two letters (`pt-BR` → `pt`); any language
  other than `en`/`pt` uses the "other" table.

- [ ] **Step 4: Run the tests** — Expected: PASS.

- [ ] **Step 5: Commit** — `git commit -m "music-video onsets: the first sound of a word from its spelling (en, pt)"`

---

### Task 2: Measuring the onset on the vocal stem

**Files:**
- Modify: `music-video/scripts/musicvideo/video/onsets.py`
- Test: `tests/test_mv_video_onsets.py`

**Interfaces:**
- Consumes: `Sound` (Task 1).
- Produces: `ONSET_SR = 44100`; `measure_onset(samples: np.ndarray, sr: int, lo: float, hi: float, guess: float,
  sound: Sound) -> tuple[float | None, float]` — the onset time in song seconds (or `None`) and a confidence 0–1,
  searching `[lo, hi]` with `guess` the current start; `samples` is the whole stem (index 0 = song 0 s).

Synthetic helpers live in the test file: `tone(f, s)`, `noise(s, hp=4000)` (white noise high-passed by FFT masking),
`click()`, `silence(s)`, concatenated at `ONSET_SR`.

- [ ] **Step 1: Write the failing tests:**

```python
def test_a_hiss_starts_the_s_word():          # silence 0.5 s, hiss 0.2 s, tone 0.4 s
    t, conf = measure_onset(audio, ONSET_SR, lo=0.40, hi=0.95, guess=0.70, sound="fricative")
    assert abs(t - 0.50) <= 0.01 and conf >= 0.5          # the aligner's guess (the vowel) was 0.20 s late

def test_a_burst_starts_the_stop_word():      # silence 0.5 s, 5 ms click, 30 ms silence, tone
    t, conf = measure_onset(audio, ONSET_SR, lo=0.30, hi=0.80, guess=0.60, sound="stop")
    assert abs(t - 0.50) <= 0.01 and conf >= 0.5

def test_a_voiced_word_starts_on_the_voice_not_the_breath():   # silence, soft broadband breath 0.15 s at 0.45, tone at 0.60
    t, conf = measure_onset(audio, ONSET_SR, lo=0.35, hi=0.85, guess=0.50, sound="voiced")
    assert abs(t - 0.60) <= 0.01 and conf >= 0.5

def test_a_voiced_word_after_a_dip():         # tone A to 0.48, 40 ms near-silence, tone B from 0.52
    t, conf = measure_onset(audio, ONSET_SR, lo=0.30, hi=0.80, guess=0.40, sound="voiced")
    assert abs(t - 0.52) <= 0.01

@pytest.mark.parametrize("sound", ["fricative", "stop", "voiced"])
def test_no_clear_event_gives_no_onset(sound):  # one steady tone through the whole window, and pure silence
    for audio in (tone(440, 1.5), silence(1.5)):
        t, conf = measure_onset(audio, ONSET_SR, lo=0.3, hi=1.0, guess=0.6, sound=sound)
        assert t is None or conf < 0.5
```

  Each planted case first asserts the guess is wrong by the planted amount (e.g. `assert abs(0.70 - 0.50) > 0.15`) so
  the test can fail.

- [ ] **Step 2: Run them to make sure they fail** — Expected: FAIL (`ImportError: measure_onset`).

- [ ] **Step 3: Implement `measure_onset`** — a magnitude STFT over `[lo − 0.1, hi]` with a 5 ms hop, computed twice
  (20 ms and 40 ms Hann windows) with `numpy.fft.rfft`; band energies in dB. Per class (spec "The measurement"):
  fricative = first frame where the 4–12 kHz band rises a clear margin over its floor (the median of the 100 ms before
  `lo`) and stays up ≥ 30 ms while exceeding the 100–1500 Hz band; stop = the largest positive broadband spectral flux
  that follows a dip; voiced = the first sustained rise of the 100–1500 Hz band out of the window's minimum, ignoring
  rises that are high-band only. Confidence from the margin and sharpness, scaled 0–1; if the two windows' onsets
  differ by > 25 ms, return the 20 ms onset with confidence `min(conf, 0.3)`. Keep thresholds as module constants.

- [ ] **Step 4: Run the tests** — Expected: PASS. Tune constants until they do; don't loosen the asserted tolerances.

- [ ] **Step 5: Commit** — `git commit -m "music-video onsets: measure a word's first sound on the vocal stem"`

---

### Task 3: Refining the words, and which words a fix touches

**Files:**
- Modify: `music-video/scripts/musicvideo/video/timing.py` (the `Word` dataclass, `apply_fixes`, `build_timing`)
- Modify: `music-video/scripts/musicvideo/video/onsets.py`
- Test: `tests/test_mv_video_onsets.py`, `tests/test_mv_video_timing.py`

**Interfaces:**
- Consumes: `first_sound`, `measure_onset`, `ONSET_SR` (Tasks 1–2).
- Produces:
  - `Word` gains `sound: str = ""`, `onset_conf: float | None = None`, `moved: float = 0.0`; `source` gains the value
    `"onset"`.
  - `fixed_indices(words: list[Word], fixes: list) -> set[int]` in `timing.py` — the indices `apply_fixes` would
    change; `apply_fixes` uses the same matching (extract it, don't duplicate it).
  - `refine_onsets(words: list[Word], samples: np.ndarray, sr: int, lang: str, keep: set[int]) -> list[Word]`.
  - `build_timing` writes `sound` for every word with one, and `onset_conf` / `moved` for words that have them
    (`moved` rounded to 3 decimals; omitted when `sound` is empty).
  - `ONSET_MIN_CONF = 0.5`, `ONSET_EARLY_S = 0.30`, `ONSET_LATE_S = 0.25`.

- [ ] **Step 1: Write the failing tests:**
  - `test_fixed_indices_names_the_words_a_fix_touches` — two words "Rain" at 1.0 and 5.0; fixes
    `[{"at": 5.1, "word": "rain", "shift": 0.1}, {"word": "nine", "show": "9"}]` → `{1}`.
  - `test_refine_moves_an_s_word_onto_its_hiss` — synthetic stem with a hiss at 0.50 and a vowel at 0.70; words
    `[Word("sun", 0.70, 1.0, 0.9)]` → start `0.50 ± 0.01`, `source == "onset"`, `sound == "fricative"`,
    `moved ≈ −0.20`, end unchanged.
  - `test_refine_skips_kept_words` — same stem, `keep={0}` → start stays 0.70, `sound == "fricative"`, `moved == 0`.
  - `test_refine_trims_the_previous_word` — previous word 0.10–0.62, an s-word guessed at 0.70 with hiss at 0.50 →
    previous end becomes 0.50 (the new start); no overlap.
  - `test_refine_will_not_squeeze_the_previous_word` — previous word 0.46–0.62 → the s-word keeps 0.70 (trim would
    leave 0.04 s < `MIN_WORD_S`).
  - `test_refine_never_goes_below_zero` — the first word guessed at 0.10 with a hiss at 0.0 → start ≥ 0.0.
  - `test_refine_keeps_the_start_without_a_clear_event` — steady tone → start unchanged, `moved == 0`.
  - `test_build_timing_writes_the_onset_fields` — a word with `sound="stop", onset_conf=0.8, moved=-0.05` →
    `{"sound": "stop", "onset_conf": 0.8, "moved": -0.05}` in its `timing.json` entry; a word with `sound=""` has none
    of the three keys.

- [ ] **Step 2: Run them to make sure they fail** — Expected: FAIL (`ImportError` / missing fields).

- [ ] **Step 3: Implement** `fixed_indices`, the `Word` fields, the `build_timing` keys, and `refine_onsets`: for each
  word not in `keep`, `sound = first_sound(text, lang)`; window `lo = max(0, start − 0.30, prev.start + MIN_WORD_S)`,
  `hi = min(start + 0.25, end − MIN_WORD_S)`; `measure_onset`; move only when `conf ≥ 0.5` and the previous word's
  trimmed length stays ≥ `MIN_WORD_S` (use `too_short`); every non-kept word records `sound` and `onset_conf`.

- [ ] **Step 4: Run the tests** — `uv run pytest tests/test_mv_video_onsets.py tests/test_mv_video_timing.py -q` —
  Expected: PASS (and the existing timing tests still pass).

- [ ] **Step 5: Commit** — `git commit -m "music-video onsets: refine word starts, skipping words a fix touches"`

---

### Task 4: `align` uses it, per video, with a CLI override and a summary

**Files:**
- Modify: `music-video/scripts/musicvideo/video/align.py`
- Modify: `music-video/scripts/musicvideo/cli.py` (`cmd_align`, the `align` parser)
- Modify: `music-video/studio/template/video.yaml`
- Modify: `music-video/studio/kit/types.ts` (`TimingWord`)
- Test: `tests/test_mv_video_align.py`

**Interfaces:**
- Consumes: `refine_onsets`, `fixed_indices`, `ONSET_SR` (Task 3).
- Produces:
  - `align(ws, spec_id, lang="en", force=False, runner=None, onsets: bool | None = None) -> AlignResult`;
    `None` means "read the video's setting".
  - `onsets_setting(ws: Workspace, spec_id: str) -> bool` — `ws.video_dir(spec_id) / "video.yaml"` key `onsets`;
    missing file/key → `False`.
  - `AlignResult` gains `onsets: str` (one of `"on (video.yaml)"`, `"off (not set in video.yaml)"`,
    `"off (video.yaml)"`, `"on (--onsets)"`, `"off (--no-onsets)"`) and `moves: list[dict]` (`{"i", "text", "start",
    "moved"}` for every moved word, biggest `|moved|` first).
  - CLI: `align --onsets` / `--no-onsets` (mutually exclusive; default `None`).
  - `TimingWord` gains `sound?: string; onset_conf?: number; moved?: number`.

- [ ] **Step 1: Write the failing tests** (extend `fake_worker` use; a test writes its own synthetic `vocals.wav` into
  `video_song(...).paths.vocals` before `align`, so the fake worker keeps it):
  - `test_onsets_are_off_without_the_setting` — no `video.yaml` → timing equals a run with `onsets=False`;
    `result.onsets == "off (not set in video.yaml)"`; no word has `moved`.
  - `test_onsets_follow_video_yaml` — the fixture lyrics are "Headlights on the empty road tonight / Keep on driving
    to the dawn" and `fake_worker` starts word *i* at `0.2 + 0.3·i`, so "the" (word 2, a fricative) is at 0.80.
    `video.yaml` with `onsets: true` and a stem with a tone through "on", silence, a hiss at 0.65 and a tone from
    0.80 → "the" starts at `0.65 ± 0.01`, "on" ends at that start; `result.onsets == "on (video.yaml)"`.
  - `test_a_cli_override_wins_for_one_run` — `onsets: true` in `video.yaml`, `align(..., onsets=False)` → nothing
    moved and `video.yaml` unchanged on disk.
  - `test_a_shift_fix_keeps_its_old_meaning` — `onsets: true`, a voice onset 0.1 s before "Headlights" (0.1), and the existing
    `{"at": 0.2, "word": "Headlights", "shift": 0.1}` fix → start `0.3` (old start + shift), `source == "fixed"`.
  - `test_cli_summary_reports_onsets` — `main(["align", id, "--lang", "en", "--onsets"])` prints a line starting
    `onsets: on (--onsets):` with the moved count.
  - `test_the_template_switches_onsets_on` — `yaml.safe_load(template video.yaml)["onsets"] is True`.

- [ ] **Step 2: Run them to make sure they fail** — Expected: FAIL.

- [ ] **Step 3: Implement** — in `align`, after `snap_to_voice`: resolve the setting; when on, decode
  `p.vocals` with `decode_mono(p.vocals, ONSET_SR)` and call
  `refine_onsets(words, samples, ONSET_SR, lang, fixed_indices(words, fixes))` (load `fixes` before this point). In
  `cmd_align`, print after the `repaired:` line:
  `onsets: <state>: <n> of <total> words moved (median <±s> s); biggest: <clock> <word> <±s> s, …` (five biggest;
  `onsets: <state>` alone when off). Template `video.yaml` gains, after `lang: en`:

```yaml
# Word starts on the first sound (hiss, burst or voice), measured on the vocals. Videos made before 0.8.3 have no
# such line and keep their timing; set it to true to switch one on.
onsets: true
```

- [ ] **Step 4: Run** `uv run pytest tests/test_mv_video_align.py -q` — Expected: PASS.

- [ ] **Step 5: Commit** — `git commit -m "music-video align: word starts on the first sound for new videos (onsets in video.yaml)"`

---

### Task 5: What the user sees and is told

**Files:**
- Modify: `music-video/scripts/musicvideo/video/timing_editor.html` (the word-mark loop, ~line 400)
- Modify: `music-video/skills/make/SKILL.md` (step 4 Timing, ~lines 200–240)
- Test: `tests/test_mv_video_timing_editor.py`

**Interfaces:**
- Consumes: the `sound` key in `timing.json` (Task 3).

- [ ] **Step 1: Write the failing test** — `test_the_editor_labels_each_mark_with_its_sound`: the served page source
  contains the label map `{fricative: "F", stop: "S", voiced: "V"}` keyed on `wd.sound`.

- [ ] **Step 2: Run it** — Expected: FAIL.

- [ ] **Step 3: Implement** — after the word's small label (`cx.fillText(wd.text, x + 4, y)`), draw the class letter
  just left of the mark at 11 px in a muted colour when `wd.sound` is set; nothing when absent. In `SKILL.md` step 4:
  bad words → write `start:` (and `end:`) entries, drop the `shift: 0.2` example; add one line: new videos have
  `onsets: true` (word starts placed on the first sound: an s on its hiss, a p on its burst, a vowel on the voice);
  existing videos keep their timing unless the user asks to switch theirs on (`onsets: true` in its `video.yaml`).

- [ ] **Step 4: Run** `uv run pytest tests/test_mv_video_timing_editor.py -q` — Expected: PASS.

- [ ] **Step 5: Commit** — `git commit -m "music-video timing editor and skill: show each word's first sound; fixes as start times"`

---

### Task 6: Tune on the user's own corrections, then release

**Files:**
- Create (outside the repo, never committed): `<session scratchpad>/score_onsets.py`
- Modify: `music-video/scripts/musicvideo/video/onsets.py` (constants only, if tuning changes them)
- Modify: `music-video/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
  `music-video/scripts/musicvideo/__init__.py` (version `0.8.3`)

- [ ] **Step 1: Write the scoring script** — for each song in the workspace whose `videos/<id>/timing-fixes.yaml` has
  `start:` entries (dragged in the editor): load its cached `vocals.wav` and `aligned.json`/`transcript.json`, run
  `reconcile` → `snap_to_voice` → `refine_onsets` with `keep=set()`, and report per sound class the median and 90th
  percentile `|start − fixed start|` for the refined start and for the pre-onsets start, plus how many words moved.
  Read-only: it writes nothing into the workspace or the work folder.

- [ ] **Step 2: Run it** — Expected: the refined median error is below the pre-onsets median for every class with ≥ 10
  words. If not, adjust `onsets.py` constants, re-run Tasks 2–3 tests, and re-score. Record the final table in the
  commit message.

- [ ] **Step 3: Bump the version to 0.8.3** in the three files.

- [ ] **Step 4: Run the gate** — `uv run pytest -q` — Expected: all pass (packaging and privacy included).

- [ ] **Step 5: Commit** — `git commit -m "music-video 0.8.3: word starts on the first sound for new videos"` (with the
  scoring table in the body).
