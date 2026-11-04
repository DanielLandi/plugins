# music-video

Turn a theme into a finished music video with Claude Code: lyrics, a song made in your own Suno account, word-level
timings, and a code-rendered 2D/3D video with subtitles, a 9:16 cut and a thumbnail. You approve every stage.

> **Licences to know first.** The videos are rendered with [Remotion](https://www.remotion.dev). Remotion is free
> for individuals and companies of up to 3 people; larger companies need a Remotion company licence
> ([remotion.dev/license](https://www.remotion.dev/license)). The licence is between you and Remotion. Songs are
> made in your own Suno account under Suno's terms for your plan. The plugin itself is MIT; bundled assets are
> listed in [THIRD_PARTY_NOTICES.md](./THIRD_PARTY_NOTICES.md).

## What you get

- **A song:** 2–3 lyric options in chat, 2–3 musical directions created in Suno, a table of takes to listen to.
  Only the take you name is downloaded.
- **Timings:** every sung word timed (vocal separation + forced alignment, repaired against a transcription), plus
  tempo, beats, sections and big moments. A karaoke preview lets you check sync before any video work, and the [timing editor](#fixing-word-timings-by-eye-and-ear) lets you drag any word that is off onto where it is sung.
- **A video:** a written look, a storyboard with a reason for every cut, real scenes in React (2D, or 3D with the
  bundled kit: camera rigs on the song clock, extruded 3D lyrics, CC0 models), motion blur by sub-frame averaging,
  subtitles, and automatic checks (black, flash or frozen frames, sync, size) before you see anything.
- **Deliverables:** the 16:9 full song, a 9:16 cut, a thumbnail, and `.lrc`/`.srt`/`.vtt` lyrics.

## Fixing word timings by eye and ear

Subtitles that light up each word as it is sung need every word's start right to about a tenth of a second.
Alignment gets most words there; the rest (a whispered word, a word after a long held note) you fix in the
**timing editor**, a page on your own computer. The make skill offers it with the karaoke preview, or run
`edit-timing <id> --open`.

![The timing editor: the line being sung, each word's mark over the vocal waveform, and a spectrogram underneath](../docs/images/music-video-timing-editor.png)

*A demo line (spoken by macOS `say` over a synth chord), with "flicker," just moved and "Streetlights" selected.*

- **Ten seconds at a time:** the vocal waveform with 0.1 s ticks, the beats as dots along the top, and a mark at
  each word's start with a bar to its end. The line being sung is shown above, and the word being sung large below.
- **A spectrogram under the waveform** shows which pitches sound when, so a word's first sound is easy to place:
  an s, f or sh is a haze high up that can start several frames before the vowel, a p, t or k a thin vertical line,
  a vowel or an m, n or l a stack of bright bands low down. A breath before a phrase is a faint haze, not the start.
- **Drag a mark** (in the waveform or the spectrogram) to move a word: it keeps its length. Drag the handle at the
  end of its bar to move its end. Arrow keys nudge the selected word by 10 ms (Shift: 100 ms).
- **Listen around it:** Space plays from the cursor, B goes back to the start of the line. **Vocals** switches the
  sound and the pictures to the separated voice alone, without the band.
- **Audio delay:** Bluetooth headphones play the sound about 0.2 s late. Slide it while playing until the
  playhead meets the sound, so you judge words by ear where you hear them.
- **Save** writes one entry per moved word to the video's `timing-fixes.yaml`, then re-aligns and re-analyses the
  song with your fixes. The fixes stay with the video, so a new alignment never loses them, and Undo works until you
  save.

The page only answers requests from your own computer. **S** hides the spectrogram, **F** colours the waveform by
frequency, and the page's help lists every key.

## Requirements

- **macOS.** Windows is not tested yet (the commands avoid bash-only syntax so it can follow).
- **Claude Code**, and **Chrome with the Claude in Chrome extension**, signed in to **your own Suno account**
  (a paid plan, for downloads and commercial terms).
- **uv** ([install](https://docs.astral.sh/uv/getting-started/installation/)), **Node 20+** and **ffmpeg**
  (`brew install ffmpeg`). `doctor` checks them and says what is missing.
- About 4 GB of disk in your cache folder: the video engine's packages (1.7 GB) and the alignment models.

## Install

In Claude Code:

```
/plugin marketplace add DanielLandi/plugins
/plugin install music-video@daniellandi
```

Then ask: *"make a music video about a night drive through the city"*. The `music-video:make` skill runs
`doctor` (installs the video engine once) and `init` (asks your artist name and your Suno plan's billing day and
downloads per cycle), then starts at the concept.

## Where things go

| Folder | Default (macOS) | What's in it |
|---|---|---|
| **Project** | `~/Documents/Music Videos/` (`init --path` for another) | `config.yaml`, `specs/<id>.yaml` (one per song), `albums/<album>.yaml`, `videos/<id>/` (each video's documents and scene code). Small: keep it in git if you like. |
| **Install** | `~/Library/Application Support/music-video/` | the engine (Remotion, its browser, compilers, three.js) and the alignment models, installed once by `doctor` |
| **Work** | `~/Library/Caches/music-video/work/<id>/` | everything regenerable: timings, vocals, previews, renders, checks. `clean <id>` frees it. |
| **Results** | `~/Movies/Music Videos/` (`results_dir`) | `<id>/`: the final videos, thumbnail, subtitles, the song and `web/` (the live page); `albums/<album>/`: tagged MP3s and `manifest.json` |

Nothing is stored in the plugin folder, which is replaced on every update.

## How the Suno steps work

Claude drives suno.com in your own Chrome, signed in as you, through the Claude in Chrome extension. There are no
unofficial APIs, no cookie replay and no captcha solving: when Suno asks "Verify you are human", Claude stops and
asks you. Every form is read back and compared with the spec before Create. A download is recorded against your
plan's downloads (`downloaded`) before the Download click, and only for a take you named.

## Commands

The skills run these for you; each is `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" <command>`.

| Command | What it does |
|---|---|
| `doctor` | check uv, Node, ffmpeg; install the video engine into the install folder |
| `init` | create or point at your workspace |
| `new`, `validate`, `round`, `downloaded`, `status` | song specs, Create rounds, the download budget |
| `ingest`, `album` | file a downloaded MP3, tagged, into its results or album folder; rebuild an album's `manifest.json` |
| `align`, `analyze`, `preview` | word timings, the song map, a karaoke preview |
| `edit-timing` | drag words onto the vocal waveform and its spectrogram to fix their timing, then save |
| `new-video`, `typecheck`, `paths`, `clean` | start a video from the template, check its code, print its folders, free its working files |
| `loop`, `web` | a seamless audio loop of a song; a live web page of a video (looping, optional sound) |
| `studio`, `still`, `stills`, `render`, `blur`, `board` | Remotion Studio, stills, renders, motion blur, the transition board |
| `mux`, `qc` | add the song to a silent render (with any lifts in the video's `song-fixes.yaml`); check a render |
| `version`, `review` | keep each checked render or still as a numbered version of its scene; a local page that plays any two versions in sync (side by side, wipe, flip) |
| `library` | everything in your results folder (videos, songs, lessons) as one page any phone, tablet or TV browser on your home network can play from; `library install` keeps it running from login (macOS) |

## Song generators and albums

A song spec names its generator (`generator: suno`), with that generator's settings in its own block; Suno is the
first, and everything specific to it lives in `skills/song/references/generators/suno/`. Songs can belong to an
album: `albums/<album>.yaml` gives the title, year and cover, and can credit a different artist and album name per
style; the album's folder in results holds the tagged MP3s and a `manifest.json` for a site or player.

## Your library at home

`music-video library install` (macOS) starts a small read-only web server at every login and prints its address,
for example `http://your-mac.local:8642/`. Open it on a phone, a tablet or a TV's browser on the same network: every
project in the results folder, newest first, with its thumbnail, subtitles, a Loop button (for a film left playing
on a TV) and Play all; songs play in the page; a live web page is linked. AirPlay or cast from the player to send a
video to the TV. Working folders (any folder whose name starts with `_` or `.`, such as a lesson's `_source`) are
never listed or served. It is open to anyone on your home network, with no password: do not forward its port to
the internet. It answers only requests addressed to the computer by its address or its `.local` name (so a website
cannot read it through a browser at home). `library` prints the address, `library serve` runs it in the foreground (any platform), `library
uninstall` stops it starting at login. After a plugin update, run `library install` again to refresh its copy.

## The live web page

`web <id>` builds a static page that draws the video's `web.tsx` live in the browser with Remotion Player, on a
loop, with an optional seamless audio loop (`loop <song>`) behind a sound button. Copy `results/<id>/web/` to any
static host.

## The 3D kit and motion blur

`@mv/kit/three` gives a full-frame `<Stage>`, a `<CameraRig>` whose keys sit on the song clock (land a key on each
sung word), extruded lyrics (`<Text3D>`, `<Letters>`), a `<SkyDome>`, a `<Model>` loader for the bundled CC0 GLBs,
a NaN-safe post chain, and a finishing pass: a film-print post (`FinishPost`), paper with thickness, carved frames
and relief maps that give flat things depth. Lyrics drawn on things (letters, signs, screens) use canvas surfaces
whose fonts are loaded before a frame is captured. `blur` renders sub-frames and averages them with a centred shutter (32 samples gives
film-like blur on camera moves); a render that shows no progress for 15 minutes is killed and started again
(`--stall`, `--retries`).

## Licence

MIT for the plugin's own code. Third-party code, models and fonts: [THIRD_PARTY_NOTICES.md](./THIRD_PARTY_NOTICES.md).
