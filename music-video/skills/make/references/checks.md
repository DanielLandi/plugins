# Error checks

Objective errors that must never reach the user. Run them before showing any render. When the user catches an
error that no check covered, propose a new row here (with their OK).

| id | What is wrong | How it is checked |
|---|---|---|
| format | wrong size, frame rate or codec | `qc --size …` |
| colour | the video is not tagged BT.709 (primaries, transfer, matrix; tv range), so players guess its colours | `qc` (renders from this engine are BT.709; an ffmpeg step stamps `setparams=…bt709…`) |
| duration | the video is not the song's (or the excerpt's) length | `qc` |
| black | a black stretch that is not a declared hold (3 frames or more) | `qc` (`--hold` for designed ones) |
| flash | a near-blank, dark or white run of 1–6 frames that is not true black (a scene captured before it finished loading) | `qc` |
| frozen | a frozen stretch that is not a declared hold | `qc` |
| audio | missing, the wrong sound, cut short, or out of sync | `qc` (the full cut is AAC: sync at 0 ms and full length; excerpts ±1 frame); skipped, and said, for a placeholder video or `qc --silent` |
| frame-sheet | a frame that makes no visual sense: half-loaded, cut off, placeholder text, overlapping | scan the overview sheet for structure, then read every paged sheet (`qc/<stem>-sheet-NN.png`, videos over 20 s), every tile |
| no-blank-cuts | a transition that empties, whites out or floods the frame | `board <id>` |
| draft-scale | a transition that renders black or flat at a reduced scale (`pixelate` goes black at `--scale=0.5`) | drafts render at full scale; the `qc` black check (3 frames) |
| text-safe-area | text touching the frame edge or under 9:16 platform buttons | text inside `<SafeArea>`/`LyricLayer`; check the sheet |
| lyric-sync | a highlighted word that is not the word being sung | watch three moments of every sample/draft against the audio |
| spelling | an on-screen word that differs from the lyrics | read every line on the paged sheets (`qc/<stem>-sheet-NN.png`) against `lyrics.md`; the overview is too small for words |
| 3d-blank | part of a 3D frame goes flat or black after bloom | a NaN pixel survives into the bloom pass: keep the kit's `SanitizeShader` before bloom |
| 3d-timeout | a render times out on a heavy first frame (a 3D canvas created mid-song) | `blur` already allows 5 min per frame; for `render`, pass `--timeout=300000` |
| lyric-early | a line can be read before it is sung (a later sign seen from the street, a card already written), where the look says it appears as sung | read the sheet tiles before each line's time |
| framing | a character or key prop cut by the frame edge (16:9 or 9:16) | every sheet tile: the characters are whole; stand the camera back rather than zoom |
| flicker | a region that changes for 1–3 frames and changes back: two faces in one plane (a prop's base on the ground, panels drawn over each other), a decal off its surface, a shader threshold, a glint | `qc` flicker scan (a designed blink or strobe: `--hold`); never share a plane: lift a prop's base a few mm, drop covered panels; watch slow camera moves at full scale |
| pop | something appears or vanishes between two frames (an entrance with no animation, a model swapped in) | `qc` pop scan; step the frames it names (`animation.md`, nothing pops in) |
| hard-cut | a one-frame picture change inside a scene that nobody designed (a camera key jump, a scene starting late) | `qc` hard-cut scan; scene changes come from `analysis.json`, designed in-scene cuts are listed in `video.yaml` `cuts:` |
| jitter | a camera that wanders and comes back within a second, more than once (not a move, not a designed jolt) | `qc` jitter scan (skipped when `video.yaml` says `jolts: true`); `shot-design.md`, monotone and decisive |
| buried | a character sunk into a floor or table | place by the model's lowest point, not its origin; look at the stills at each scene's start |
| left-behind | one element of the outgoing scene stays alone in frame (an anchor held for a match cut) after its group has left | the board's 35% and 65% panels; it leaves with its group, or the cut changes |
| word-late | a word appears seconds after it is sung (aligned late after a pause or a held note) | listen at every gap of 1 s or more inside a line (see step 4) |
| twitch | a body, limb or prop that snaps sideways for 1–3 frames and back while the shot moves (a lean following a curve whose curvature jumps, a key with a kink); under motion blur it shows as a smeared ghost of the body for those frames | **`qc` does not catch it** in a moving shot: step every frame of each fast move or turn of a character (`stills` of the frames around it, without blur, show the jump; with blur, look at a frame grid of every frame, not every fifth). Why: see below |

**Why qc misses a twitch under blur.** qc's motion scans compare small (320 px) copies of neighbouring frames. A
twitch is a region that leaves and comes back within three frames, which the flicker scan catches only on a still
picture: in a chase or tracking shot the camera and the character drift a few pixels every frame, so the frames
either side of the twitch already differ as much as the twitch does, and blur turns the jump into a soft ghost
whose pixels stay inside the range of its neighbours. A local scan that did see the twitch on a synthetic clip also
flagged every telephone pole passing the lens and every row of piano keys sliding by in finished clips, and still
missed a real twitch (a two-frame lean snap in a blurred downhill chase). Telling them apart needs per-pixel motion
(optical flow), which qc does not have; a plain, unblurred twitch on a steady picture is caught (as a pop or a
flicker).
