# Suno: the song skill's steps, Suno's way

The song skill's steps are the same for every generator; this file is what each step means on Suno. How to operate
each control (refs, read-back snippets, the toast watcher, the download dialog) is in `ui-map.md`; what each
setting means is in `controls.md`; starting points per genre are in `recipes.md`.

## 1. Draft: the `suno:` block

Fill the spec's `suno:` block from the genre recipe: `model`, `styles`, `exclude_styles`, `vocal_gender` (omit if
the recipe says unset), `weirdness`, `style_influence`, `variety`, `lyrics` with section tags. For an instrumental,
set `instrumental: true`, leave `lyrics` empty and omit `vocal_gender`; put `instrumental` in `styles` and
`vocals, singing, choir` in `exclude_styles`. For a set length, add `duration: <seconds>` (the map's Duration Custom).

Show the user: title · model · styles · exclude · sliders · a one-line story and the chorus. Credits are spent only
on Create, never by filling the form.

## 2. Fill

Navigate to `https://suno.com/create`. Set **every** field exactly as `ui-map.md` says (Suno remembers old values):
Advanced mode, model, lyrics, styles, title, then expand More Options for exclude, vocal gender, sliders, and
confirm Max Mode Off, My Taste Off, Duration Auto (or Custom with the spec's `duration`).

## 3. Verify

Read every field back with the map's read-back snippets and compare to the spec. An instrumental's lyrics editor
must read back empty. Lyrics are compared inside the page (embed the spec's lyrics as a JSON string; return
`{equal, diffs}`). Sliders must equal the spec value exactly; Variety's label must match.

## 4. Create

Install the toast watcher from the map, click Create, wait ~5 s, read `window.__toasts`. A rejection
(copyright/moderation) adds no rows. Accepted: two takes appear (~40 s to 2 min); collect their URLs and durations
as the map describes.

## 6. Download

Open the take's More options → Download. Select **MP3** and deselect **M4A** (it is pre-selected; formats are
multi-select); zoom to confirm only MP3 is ticked. The dialog's **Downloads N** is Suno's own count: if N is 0,
close the dialog and undo the download record. Then **Unlock & Download**; wait for the dialog to close. The file
lands in the downloads folder as `<Title>.mp3`.

## Paste card (when Chrome cannot be used)

```text
Model:            <model>
Title:            <title>
Styles:           <styles>
Exclude styles:   <exclude_styles>
Vocal gender:     <vocal_gender or "—">
Weirdness:        <n>    Style Influence: <n>    Variety: <variety>
Max Mode: Off    My Taste: Off    Duration: Auto    Download format: MP3
Lyrics:
<lyrics, or "(instrumental: leave empty)">
```
