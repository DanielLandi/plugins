# Suno UI map (v6 Create page) — mapped 2026-10-03

How to operate suno.com through the Claude in Chrome tools. Every method here
worked in the mapping session. When Suno changes its UI, fix this file first.

General rules learned:
- **Prefer element refs over coordinates.** A coordinate click on the
  Simple/Advanced tab silently did nothing; clicking the same tab by its `ref`
  (from `find`/`read_page`) worked. Screenshot coordinates and CSS viewport
  coordinates differ in scale.
- **Suno remembers form state across reloads** (Advanced mode, sliders, Variety,
  text). Never trust what is already in the form — set every field every time.
- **Hidden duplicates exist.** The Speech/Sounds tabs keep their own (hidden)
  inputs, e.g. a second Variety slider and a second title input. Always filter
  with `el.checkVisibility()`.
- Synthetic JS events (`paste`, setting `.value`) are ignored by the lyrics
  editor; use real typing there.

## Account facts (read them from the user's own account)

- Plan, the day downloads refresh, and **Downloads Remaining**: `https://suno.com/account` (use
  `get_page_text`), or the download dialog footer ("Downloads N", "Refreshes M/D/YY"). The refresh day is
  `billing_day` in the workspace's `config.yaml`; downloads per cycle is `download_budget`.
- Suno's number is the authority: it can be higher than the plan's allowance (extra or bonus downloads).
- A Create (two takes) costs credits only, never a download.

## Create page — Advanced mode (`https://suno.com/create`)

### Mode: Simple / Advanced
- Set: `find` "Advanced tab" → `computer left_click` with its `ref`.
- Read back: tab `role=tab` with text `Advanced` has `aria-selected="true"`.

### Model picker
- Set: the button whose text is `v6`/`v6-wild` next to the mode tabs. Click it
  (find by visible text), then click the option. Options, in order:
  "Create Custom Model (Beta, 100 credits)", `v6` (Pro, default), `v6-wild` (Pro),
  `v6-mini`. Escape closes it.
- Read back:
  `[...document.querySelectorAll('button')].filter(b=>b.checkVisibility()).find(b=>/^v6/.test(b.innerText.trim())).innerText.trim()`

### Lyrics (Lexical rich-text editor, `aria-label="Lyrics editor"`, role textbox)
- Set: click the editor by `ref` → key `cmd+a` → key `Delete` → `computer type`
  the full lyrics with `\n` newlines (blank lines become empty paragraphs).
- Before typing, confirm focus:
  `document.activeElement.getAttribute('aria-label')==='Lyrics editor'`.
  Once (2026-10-03, right after clicking the already-selected Advanced tab in
  the same batch) the click did not take focus and the whole typed text was lost.
- Read back (one `<p class="lyrics-paragraph">` per line):
  ```js
  const ed=[...document.querySelectorAll('[aria-label="Lyrics editor"]')].find(e=>e.checkVisibility());
  [...ed.querySelectorAll('p.lyrics-paragraph')].map(p=>p.textContent).join('\n').replace(/\n+$/,'')
  ```
- Compare to the spec's lyrics with trailing newlines stripped. Do the
  comparison **inside the page** (embed the expected text as a JSON string and
  return `{equal, diffs}`) — returning the whole text gets truncated.
- Limit: none shown in the DOM; keep within the spec's `LYRICS_MAX`.
- Long lyrics (~2,000+ chars) can make `computer type` report a CDP timeout after
  30 s even though every character arrived (2026-10-04). Don't retype: read back,
  and only re-set if the comparison fails.

### Styles (textarea, `maxlength="1000"`, placeholder changes randomly)
- Set: `form_input` on its `ref` (find "Styles textarea"). Registers fine.
- Read back: `[...document.querySelectorAll('textarea[maxlength="1000"]')].find(e=>e.checkVisibility()).value`
- Limit: **1000** chars.

### Exclude styles (input, `placeholder="Exclude styles"`, `maxlength="1000"`)
- Lives inside **More Options** — expand it first (button "More Options").
- **Whether More Options is open cannot be read from the Exclude input**: it
  stays in the DOM and passes `checkVisibility()` while collapsed (2026-10-03).
  When collapsed, the button row shows a one-line `Exclude "…"` summary under
  "More Options". Check with `find` for the Weirdness slider (or a screenshot)
  before setting sliders; slider keys sent while collapsed are silently lost.
- Set: `form_input` on its `ref`.
- Read back: `document.querySelector('input[placeholder="Exclude styles"]').value`
- Limit: **1000** chars.

### Song Title (input, `placeholder="Song Title (Optional)"`)
- Set: `form_input` on its `ref`. Two visible copies mirror each other.
- Read back: first visible `input[placeholder="Song Title (Optional)"]` `.value`.
- Limit: no `maxlength` attribute; keep titles short (spec `TITLE_MAX`).
- Suno uses the title as the downloaded file name.

### More Options group (segmented buttons; selected one has `data-selected="true"`)
| Control | Options | Default |
|---|---|---|
| Vocal Gender | Male / Female (neither selected = unset) | unset |
| Duration | Custom / Auto | Auto |
| Max Mode | Off / On | Off |
| Personalize (My Taste) | Off / On | Off |
- Set: click the option button by `ref` (`find` "Vocal Gender Male button").
- Read back:
  ```js
  const sel=(group,label)=>[...document.querySelectorAll('button')].filter(b=>b.checkVisibility())
    .find(b=>b.innerText.trim()===label && b.parentElement.parentElement.innerText.startsWith(group))
    ?.getAttribute('data-selected');
  sel('Vocal Gender','Male')  // "true" | "false"
  ```
### Duration Custom (mapped 2026-10-08)
- Clicking **Custom** replaces the Custom/Auto pair with a slider (`role=slider`,
  `aria-label="Duration"`, 10–360 s, **step 5 s**, default 180, `aria-valuetext`
  "2 minutes") plus a visible `m:ss` text input. Set it like the other sliders:
  focus from JS, `ArrowLeft repeat 100` → 10, then `ArrowRight repeat (target-10)/5`
  (120 s = 22 presses). Read back `aria-valuenow`. The Custom/Auto `data-selected`
  read-back no longer works once the slider is shown; `aria-valuenow` is the check.
- Results: with 120 s, two directions came out 1:58–2:01, one came out 3:11–3:17
  with the slider reading 120 right before Create (2026-10-08). Treat Custom as a
  strong hint, not a guarantee; check every take's length.
- Suno remembers Custom across Creates like every other control.
- 2026-10-09: a `ref` click on **Custom** did nothing (Auto stayed selected); a DOM click works:
  `[...document.querySelectorAll('button')].find(x=>x.checkVisibility()&&x.innerText.trim()==='Custom'&&x.parentElement.parentElement.innerText.startsWith('Duration')).click()`.
  With Custom 140 s, all six takes came out 2:19–2:20. Generation took 40 s to about 2 min per Create.

- To unset a vocal gender, click the selected option again and confirm both read "false"
  (verified 2026-10-03: clicking the selected option deselects it).
- **Ref clicks on Male/Female are unreliable**: on 2026-10-03 two `ref` clicks on
  Male left both options "false". A coordinate click worked, and so does a DOM click
  that checks state first (used for a 6-song batch without a miss):
  ```js
  window.__setVocal=(want)=>{ // 'male' | 'female' | 'unset'
    const b=l=>[...document.querySelectorAll('button')].find(x=>x.checkVisibility()&&x.innerText.trim()===l&&x.parentElement.parentElement.innerText.startsWith('Vocal Gender'));
    for(const l of ['Male','Female']){const on=want===l.toLowerCase(); if((b(l).getAttribute('data-selected')==='true')!==on) b(l).click();}};
  ```
  Its immediate return value lags React's re-render; trust the full read-back instead.
- Suno remembers the vocal gender across page loads, so never click blindly to "select" it.

### Sliders (`role=slider`, `aria-label` = name)
| Slider | Range | Step | Default | Read |
|---|---|---|---|---|
| Weirdness | 0–100 | 1 | 50 | `aria-valuenow` |
| Style Influence | 0–100 | 1 | 50 | `aria-valuenow` |
| Variety | 0–4 | 1 | 1 | `aria-valuetext` |
- Variety labels: 0 **Off** ("Exact style"), 1 **Normal** ("Balanced variety"),
  2 **High**, 3 **Extra**, 4 **Max**. Spec values are these labels lower-cased.
- Set (clicking does NOT give keyboard focus — focus from JS first):
  1. `javascript_tool`: `[...document.querySelectorAll('[role=slider][aria-label="Weirdness"]')].find(e=>e.checkVisibility()).focus()`
  2. `computer key ArrowLeft repeat 100` (Variety: `repeat 5`) → minimum.
     (`Home` did not reliably reach 0.)
  3. `computer key ArrowRight repeat <value>` (Variety: index of the label).
- Read back: `aria-valuenow` (number) / `aria-valuetext` (Variety label).
- Long key runs can drop a press or two (2026-10-09: Weirdness read 39 after `ArrowRight repeat 40`, Style
  Influence 68 after 70). The read-back catches it; correct with the difference (`ArrowRight repeat 1`).

### Create button (`aria-label="Create song"`)
- Set: `find` "Create song button" → click by `ref`.
- Before clicking, install a watcher so error toasts are captured (they vanish fast):
  ```js
  window.__toasts=[]; window.__obs?.disconnect();
  window.__obs=new MutationObserver(ms=>{for(const m of ms) for(const n of m.addedNodes){
    if(n.nodeType===1){const t=n.innerText?.trim();
      if(t&&t.length<400&&/copyright|error|unable|couldn|failed|limit|moderat|verify/i.test(t)) window.__toasts.push(t);}}});
  window.__obs.observe(document.body,{childList:true,subtree:true});
  ```
  After clicking, wait ~5 s and read `window.__toasts`.

## Captcha

- A **Cloudflare "Verify you are human"** box appeared on the first Create of the
  session; later Creates in the same session went straight through.
- Never solve it: stop and ask the user to tick it, then continue.

## After Create

- Two new rows appear at the top of the workspace list (right pane, "Today"),
  each titled with the song title and a `V6` badge; a spinner shows while
  generating. Both finished in ~40 s.
- Take links: `a[href^="/song/"]` whose text equals the title — DOM order =
  list order (take 1 = top). URL form `https://suno.com/song/<uuid>`.
- Duration: the `m:ss` text in the row's thumbnail
  (walk ~6 parents up from the link and match `/\d+:\d\d/`).
- Rejected requests (e.g. copyright) produce **no rows** — only a short-lived toast.

## Copyright filter

- Suno blocks lyrics it recognises as existing text, including public-domain lyrics, with a short toast and no
  new rows. Rewrite the lines (originals only, see `originals.md`).

## Download

1. On the chosen take's row: `More options` button (find it by walking up from
   the take's `a[href="/song/<uuid>"]` to the nearest `button[aria-label="More options"]`;
   tag it with a `data-probe` attribute, then `find` it to get a `ref`) → menu item **Download**.
2. Dialog "Download '<Title>'" with format options **M4A** (pre-selected!),
   **MP3**, WAV, MP4 video asset, Stems & MIDI. Formats are **multi-select**:
   click **MP3**, then click **M4A** to deselect it; zoom to confirm only MP3 has the ✓.
3. Footer shows Plan, **Downloads N** (remaining), **Refreshes M/D/YY**.
   Read N and compare with the plugin's count before clicking.
4. Button **Unlock & Download** spends one download and starts the file.
   "You've unlocked this song. You can return and download at any time." —
   the charge is per song; re-downloading an unlocked song is free.
   "Preparing…" for a few seconds (once ~25 s), then the dialog closes.
   Poll for the dialog to close for up to a minute before treating it as failed.
5. File lands in `~/Downloads` as **`<Title>.mp3`** (exactly the title,
   e.g. `Night Drive.mp3`). A second file with the same name gets Chrome's
   ` (1)` suffix.

## What Suno embeds in the MP3

- `TIT2` title; `TPE1` = the user's Suno username; `WOAS` song URL;
  `COMM` and `TXXX:comment` "made with suno; created=…; id=…"; `USLT` lyrics
  (order scrambled); `APIC` cover (small JPEG, ~7 KB); `TSSE` encoder;
  **`GEOB` "c2pa manifest store"** (C2PA content credentials — AI provenance).
- Audio: MP3 ~180 kbps, 48 kHz.
- Tagging keeps `APIC` and the `GEOB` c2pa frame, and replaces everything else.

## Known fragility

- Button labels/structure (`data-selected`, `lyrics-paragraph`, `aria-label`s)
  are Suno internals and will change. Locate by visible label first.
- The style suggestion chips under Styles change on every load — never click them.
- The right-hand detail panel may open over the list after downloads/plays; close
  with its ✕ if it hides rows.
