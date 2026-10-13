# Error checks

Objective errors that must never reach the user. Run them before showing any render. When the user catches an
error that no check covered, propose a new row here (with their OK).

| id | What is wrong | How it is checked |
|---|---|---|
| format | wrong size, frame rate or codec | `qc --size …` |
| duration | the video is not the song's (or the excerpt's) length | `qc` |
| black | a black stretch that is not a declared hold (3 frames or more) | `qc` (`--hold` for designed ones) |
| flash | a near-blank, dark or white run of 1–6 frames that is not true black (a scene captured before it finished loading) | `qc` |
| frozen | a frozen stretch that is not a declared hold | `qc` |
| audio | missing, the wrong sound, cut short, or out of sync | `qc` (the full cut is AAC: sync at 0 ms and full length; excerpts ±1 frame) |
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
| flicker | a surface that shimmers in motion: two faces in one plane (a prop's base on the ground, panels drawn over each other) | never share a plane: lift a prop's base a few mm, drop covered panels; watch slow camera moves at full scale |
| buried | a character sunk into a floor or table | place by the model's lowest point, not its origin; look at the stills at each scene's start |
| left-behind | one element of the outgoing scene stays alone in frame (an anchor held for a match cut) after its group has left | the board's 35% and 65% panels; it leaves with its group, or the cut changes |
| word-late | a word appears seconds after it is sung (aligned late after a pause or a held note) | listen at every gap of 1 s or more inside a line (see step 4) |
