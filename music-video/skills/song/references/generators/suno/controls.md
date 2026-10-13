# Suno v6 controls — what they do

How to *operate* each control in the page lives in `ui-map.md`. This file is what each control *means*, so
specs choose good values.

## Models
- `v6` — flagship, versatile, most faithful to the prompt. Default.
- `v6-wild` — for experimental ideas; less predictable. Use when a genre keeps coming out generic.
- `v6-mini` — the free-tier model; not used here.

## Text fields
- **Lyrics** — the words, with section tags in square brackets on their own line: `[Intro] [Verse 1] [Pre-Chorus]
  [Chorus] [Bridge] [Instrumental Break] [Outro]`. Structure tags are followed reliably. Performance tags
  (`[Whispered]`, `[Build Up]`, `[A cappella]`) are hints only. Backing vocals go in parentheses: `(ooh, ooh)` on
  its own line or after a lyric.
  **Instrumentals:** leave Lyrics empty (the editor's own hint: "leave this empty for instrumental"); spec
  `instrumental: true`. Say `instrumental` in Styles and exclude `vocals, singing, choir` so Suno doesn't add a
  wordless vocal.
- **Styles** — 4 to 7 comma-separated descriptors: genre + era, vocal type, 2–3 signature instruments, one
  production/mood word. Fewer than 4 → Suno fills gaps with popular defaults; more than 7 → descriptors compete.
  Max 1000 chars.
- **Exclude Styles** — what to keep out: wrong-era instruments, unwanted vocal types, harsh elements.
- **Title** — shown in Suno and used as the downloaded file name.

## Sliders and toggles
- **Weirdness** (0–100, default 50) — how conventional vs surprising. 25–35 for faithful genre pastiche; 45–60 when
  results feel generic.
- **Style Influence** (0–100, default 50) — how strictly Styles is followed. 65–80 for era-specific genres that
  drift; lower if output is stiff.
- **Variety** — `off` (exact style), `normal` (default, balanced), `high`, `extra`, `max`. Lower when aiming close
  to the spec; raise for surprises.
- **Vocal Gender** — set when the genre has a clear lead (male vocal group, female ballad singer); omit otherwise.
- **Max Mode** — consistency for longer tracks and covers; leave Off unless a take falls apart midway.
- **My Taste (Personalize)** — personalizes toward the account's listening history; leave Off so the song follows
  the spec.
- **Duration** — Auto, or Custom (10–360 s) when a video needs a set length; treat Custom as a strong hint and
  check every take's length.

## Replace Section (editing a take)
Re-sings a window of an existing take. It was tried once to re-sing a barely sung word, and both takes came back
unusable. Prefer a mix lift (the make skill's `song-fixes.yaml`); treat Replace Section as a last resort, with the
user's OK on credits. How the editor behaves:
- The window is at least 10 s long.
- The start cannot be set past the end, so set the end first.
- Each take returns the song only up to the window's end, so a fix has to be spliced back into the original.

## Copyright filter
Suno rejects lyrics it recognises, including public-domain texts. Write originals; see `originals.md`.

## Custom Models and Voices (not used by this plugin)
Custom Model: fine-tune on at least 6 tracks the user owns (Beta, 100 credits); learns arrangement and
instrumentation, not voice. Voices: a consistent singer.
