# music-video: word starts on the first sound (phoneme-aware onsets)

Date: 2026-11-10 · Status: design, awaiting approval (builder check done)

## Intent

A word's highlight (and anything keyed to it) should start on the first audible sound of the word, exactly as the
listener hears it. Today `align` takes the aligner's start (stable-ts on the demucs vocal stem), repairs a few words
from the transcription, and only moves a word that sits on silence (`snap_to_voice`). Everything finer is left to the
user, who drags words in the timing editor. The user wants the analysis trusted: `align` moves every word's start to
its measured first sound automatically.

The method comes from Imaginative Prompting's `song-timing` skill (claude-video-skills, MIT): **the onset is the first
audible energy of the word's first sound**:
- a **fricative** (s, f, sh, z, ch, th, v) at its noise onset: a sung s or f hisses 5–8 frames (≈170–270 ms at 30 fps)
  before the vowel;
- a **stop** (p, t, k, b, d, g) at its release burst;
- a **vowel or sonorant** (m, n, l, r, w, y, and vowels) at the first change into it: the voice rising after a dip;
- **never** the breath or an aspirated "h" before a phrase, and never the previous word's last consonant or a pitch
  ornament.

## Goals

1. For a video that has it switched on (every new video; see "On for new videos only"), `align` refines every word's start by the class of its first sound, measured on the vocal stem it already makes
   (`vocals.wav`), and writes the refined start into `timing.json`.
2. Each word in `timing.json` records how its start was decided: its sound class, the reason, and a confidence.
3. The align summary says how many words moved and lists the biggest moves, so the user knows what changed.
4. The timing editor shows each word's sound class, so the user sees why a mark sits where it does.
5. English and Portuguese (the languages of the user's songs) get letter-to-sound rules; any other language falls back
   to "vowel or sonorant" unless its first letter is an obvious fricative or stop.

## Non-goals

- Word **ends** stay as they are (only starts move; an end moves only to keep the word at least `MIN_WORD_S` long).
- No new stem source: no Suno stems, no new separation model. The song-timing skill prefers the generator's own stems;
  that is a separate idea (it spends the user's credits and needs Chrome).
- No beat-grid or drum-hit changes in `analyze` (a separate project from the same skill).
- No phoneme recognizer or new model download: the first sound comes from the word's spelling, the time from the
  audio.

## Anti-goals (a failure even if it technically works)

- A word that reads **before** it is sung. A start may move earlier only onto that word's own first sound (its hiss,
  its burst, or for a voiced word the voice itself rising), never onto a breath, an "h", or the previous word's tail.
  Voiced words (most of any lyric) may therefore move earlier as well as later. *(Builder check; my call.)*
- A user's manual correction being undone or doubled. `timing-fixes.yaml` always wins.
- A refinement that moves a word far on a guess. Moves are bounded, and an unsure measurement leaves the word where
  it was.

## Constraints

- Plugin rules (repo `AGENTS.md`): Windows and macOS; `encoding="utf-8"` on file I/O; argument lists for subprocesses;
  the plugin and its tests contain nothing personal (`tests/test_mv_privacy.py`).
- Analysis runs in the plugin's own Python (numpy, ffmpeg via `media.decode_mono`), not in the worker: no torch, and
  the tests never load a model. Use numpy's FFT; no new dependency (no librosa, no scipy unless it is already a
  dependency).
- Every frame of the video is a pure function of `timing.json`; nothing here changes the engine.
- Version bump: `music-video/.claude-plugin/plugin.json`, its `marketplace.json` entry and
  `scripts/musicvideo/__init__.py` agree (`tests/test_mv_packaging.py`).

## The how (decided)

### Where it runs

In `align` (`scripts/musicvideo/video/align.py`), after `reconcile` and `snap_to_voice` and **before**
`apply_fixes`:

```
words = reconcile(aligned, heard, ends)
words = snap_to_voice(words, envelope)
words = refine_onsets(words, vocals_samples, sr, lang)   # new
words = apply_fixes(words, fixes)
```

The new code lives in its own module, `scripts/musicvideo/video/onsets.py`.

### Manual fixes keep their meaning

A word that any `timing-fixes.yaml` timing entry (`shift`, `start` or `end`) will touch is **not refined**: its start
stays the pre-refinement start, so a `shift: 0.2` written against the old start still lands where the user put it.
(`show:`-only entries don't count; they change text, not time.) `apply_fixes`' matching (`norm(word)` within
`FIX_WINDOW_S` of `at`) decides which word a fix touches; compute the touched set **before** refinement, reusing that
matching rather than re-implementing it.

New fixes are absolute. Once onsets ship, the preview and the editor show the refined start, so a new `shift` would
be judged against one start and added to another. The make skill's Timing step therefore tells the agent to write
`start:` (and `end:`) entries, never `shift:`; the editor already writes absolute times. `shift:` keeps working, with
its old meaning (relative to the aligner's start), for entries that already exist. *(Builder check; my call.)*

### The first sound (spelling → class)

`first_sound(word, lang) -> "fricative" | "stop" | "voiced"`, from the word's leading letters after stripping
punctuation (and `'` in words like "'cause"):

- **English:** fricative: `s`, `sh`, `ch`, `f`, `ph`, `th`, `v`, `z`, `c` before
  `e/i/y`, `x`; also `j` and `g` before `e/i/y` (affricates: the noise onset counts). Stop: `p`, `b`, `t`, `d`, `k`,
  `c` otherwise, `q`, `g` otherwise. Voiced: everything else (vowels, `m n l r w y`, and `h`, whose breath must never
  start the word: an `h` word starts on the voice after it).
- **Portuguese:** fricative: `s`, `ç`, `c` before `e/i`, `ch`, `f`, `v`, `z`, `j`, `x`, `g` before `e/i`, and initial
  `r`/`rr` (a fricative in Brazilian Portuguese). Stop: `p`, `b`, `t`, `d`, `k`, `c` otherwise, `q`, `g` otherwise.
  Voiced: vowels, `m n l lh nh`, `h` (silent).
- Other languages: the English table for `s f v z p b t d k`, voiced otherwise.

### The measurement (on `vocals.wav`)

Decode `vocals.wav` a second time for this, at 44.1 kHz mono: at 16 kHz the high band ends below 8 kHz, and much of
a sung s/sh's energy (and all that separates hiss from breath) sits above it. One extra ffmpeg pass is fine.
*(Builder check; my call.)* Use a short-time spectrum every 5 ms (window
~20 ms). For each word, search a window around its current start: from `start - 0.30 s` (but not before the previous
word's start + `MIN_WORD_S`, nor before the previous word's end minus a small overlap of 0.05 s) to `start + 0.25 s`
(but not past the word's end − `MIN_WORD_S`).

- **Fricative:** the high band (4–8 kHz) energy against its own floor just before the window; the onset is the first
  5 ms frame where that band rises above the floor by a clear margin and stays up for ≥ 30 ms, provided the high band
  dominates the low band there (hiss, not a voiced note).
- **Stop:** the largest positive broadband spectral flux in the window that follows a dip (the closure); the onset is
  that frame.
- **Voiced:** the first frame where the low/mid band (100–1500 Hz) energy rises from a dip to a sustained level, the
  dip being the minimum between the previous word and the current start. A rise that is only high-band (a breath)
  doesn't count.

Each measurement yields a time and a confidence (0–1) from how clear the event is (margin over the floor, how sharp the
rise). Following the skill's "measure twice" rule, measure with two window sizes (e.g. 20 ms and 40 ms); if the two
onsets differ by more than 25 ms, the confidence drops below the move threshold.

### When a word moves

- Confidence ≥ a threshold (start at 0.5; tune it as in Verify) **and** the move is within the window: the start
  moves to the onset. Its end stays, unless that leaves it shorter than `MIN_WORD_S`.
- **No overlaps.** A start that moves earlier than the previous word's end trims that word's end to the new start, as
  the timing editor does when a start is dragged into the word before it. If the trim would leave the previous word
  shorter than `MIN_WORD_S`, the start doesn't move. *(Builder check; my call.)*
- Otherwise the word keeps its start.
- A moved word keeps its `source` history readable: new value `onset` in `Word.source`
  (`align | transcript | snapped | onset | fixed`).

### What `timing.json` records

Each word gains three optional fields (`version` stays 1: readers ignore unknown keys; check the kit's `TimingWord`
type and add them as optional):

```json
{"i": 12, "text": "sunlight", "start": 31.418, "end": 31.9, "conf": 0.82, "source": "onset",
 "sound": "fricative", "onset_conf": 0.74, "moved": -0.19}
```

`moved` is the refinement in seconds (negative = earlier); 0 when not moved. Words a fix touched get `"sound"` but no
`moved`.

### What the user sees

- The `align` summary gains a line: `onsets: 87 of 214 words moved (median −0.07 s); biggest: 0:31.4 sunlight −0.19 s,
  …` (the five biggest), after the existing repair line.
- The timing editor shows the sound class next to each word's mark (a small letter: F, S or V, or a tooltip). Dragging
  still writes a fix entry; nothing else in the editor changes.

### On for new videos only (the user's decision)

The user decided: **every current video stays as it is; only new videos get onsets.** The choice is a setting kept with
each video, so the timing editor's save and every re-render (both re-run `align` with no flag) respect it.

- `video.yaml` gains `onsets: true | false`. The template (`studio/template/video.yaml`) writes `onsets: true`, with a
  one-line comment, so every video made from now on has it on.
- `align <song>` reads `onsets` from the song's video folder (`ws.video_dir(<song id>)/video.yaml`, the same folder the
  editor reads `lang` from). **A missing file or a missing key means off**, so every existing video, and a song
  aligned with no video yet, re-aligns exactly as before. Nothing rewrites existing `video.yaml` files.
- `align --onsets` / `--no-onsets` override the setting for one run (for comparison); they don't change `video.yaml`.
  To switch an existing video on, the user (or the agent, with their OK) sets `onsets: true` in its `video.yaml`.
- The align summary says which applied: `onsets: on (video.yaml)`, `onsets: off (not set in video.yaml)`, or
  `… (--onsets)`.

## Verify

- **Unit tests** (`tests/test_mv_video_onsets.py`) on synthetic audio built in numpy: silence then white noise then a
  tone (a "s" word) must start at the noise onset; a click after silence then a tone (a stop) at the click; a breath
  (soft noise) then a tone for an `h` word at the tone, not the breath; a word whose window has no clear event keeps its
  start. Spelling tables for English and Portuguese, including `sh/ch/th/ph`, soft `c/g`, Portuguese initial `r`, `lh`,
  `nh`, `ç`.
- **Fix precedence:** a word with a `shift` fix ends at old start + shift, not refined start + shift.
- **Each check can fail:** the synthetic tests assert the old start is wrong by the planted amount before asserting the
  new one is right.
- **Tuning on real ground truth** (maintainer, local, never committed): the user's existing `timing-fixes.yaml`
  entries made in the timing editor are words dragged onto their first sound. A local scoring script, kept outside the
  repo, aligns those songs with onsets on (ignoring the fixes) and reports the error against the fixed starts, per sound
  class. Thresholds are tuned until the median error beats the pre-onsets start. This check gates the version bump.
  *(Builder check; my call.)*
- **On a real song:** align one of the user's songs with and without onsets, and compare the moves with the
  waveform/spectrogram in the timing editor and the karaoke preview.
- `uv run pytest -q` passes; the version is bumped.

## Left to the builder

- Exact band edges, window sizes, thresholds and the confidence formula: tune them on the synthetic tests, then
  sanity-check on a real song.
- How the summary formats times (reuse `timing.clock`).
- Whether the editor shows the class as a letter or a tooltip.
