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
  tempo, beats, sections and big moments. A karaoke preview lets you check sync before any video work.
- **A video:** a written look, a storyboard with a reason for every cut, real scenes in React (2D, or 3D with the
  bundled kit: camera rigs on the song clock, extruded 3D lyrics, CC0 models), motion blur by sub-frame averaging,
  subtitles, and automatic checks (black or frozen frames, sync, size) before you see anything.
- **Deliverables:** the 16:9 full song, a 9:16 cut, a thumbnail, and `.lrc`/`.srt`/`.vtt` lyrics.

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

```
~/Movies/Music Videos/      your workspace (init --path to choose another)
  config.yaml               artist, billing_day, download_budget, downloads_dir, videos_dir, media_dir
  specs/<id>.yaml           one song spec per song: Suno settings, rounds, the kept take
  videos/<id>/              the video's code and documents (look, storyboard, notes, journal, scenes)
  media/<id>/               song, timings, renders, deliverables (media_dir can point anywhere else)
```

Nothing personal is stored in the plugin folder, which is replaced on every update. Keep `videos/` and `specs/`
in git if you like; keep `media/` out of it (or point `media_dir` elsewhere so large files never sit next to code).

## How the Suno steps work

Claude drives suno.com in your own Chrome, signed in as you, through the Claude in Chrome extension. There are no
unofficial APIs, no cookie replay and no captcha solving: when Suno asks "Verify you are human", Claude stops and
asks you. Every form is read back and compared with the spec before Create. A download is recorded against your
plan's downloads (`downloaded`) before the Download click, and only for a take you named.

## Commands

The skills run these for you; each is `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" <command>`.

| Command | What it does |
|---|---|
| `doctor` | check uv, Node, ffmpeg; install the video engine into the cache |
| `init` | create or point at your workspace |
| `new`, `validate`, `round`, `downloaded`, `status` | song specs, Create rounds, the download budget |
| `ingest` | file a downloaded MP3 into the song's media folder, tagged |
| `align`, `analyze`, `preview` | word timings, the song map, a karaoke preview |
| `new-video`, `typecheck`, `paths` | start a video from the template, check its code, print its folders |
| `studio`, `still`, `stills`, `render`, `blur`, `board` | Remotion Studio, stills, renders, motion blur, the transition board |
| `mux`, `qc` | add the song to a silent render; check a render |

## The 3D kit and motion blur

`@mv/kit/three` gives a full-frame `<Stage>`, a `<CameraRig>` whose keys sit on the song clock (land a key on each
sung word), extruded lyrics (`<Text3D>`, `<Letters>`), a `<SkyDome>`, a `<Model>` loader for the bundled CC0 GLBs,
and a NaN-safe post chain. `blur` renders sub-frames and averages them with a centred shutter (32 samples gives
film-like blur on camera moves).

## Licence

MIT for the plugin's own code. Third-party code, models and fonts: [THIRD_PARTY_NOTICES.md](./THIRD_PARTY_NOTICES.md).
