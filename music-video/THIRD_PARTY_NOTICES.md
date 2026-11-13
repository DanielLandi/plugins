# Third-party notices

The plugin's own code is MIT (see `LICENSE`). It ships or installs the following, each under its own licence.

## remotion-transitions (MIT, vendored unmodified in `studio/transitions/`)

Copyright (c) 2026 GTKottman and contributors. MIT License; the full text is in `studio/transitions/LICENSE`.
It is updated only by re-vendoring (`studio/tools/vendor-transitions.sh`), never edited in place.

## claude-video-skills (MIT, adapted into `skills/make/references/`)

Parts of the make skill's references are adapted from Imaginative-Prompting/claude-video-skills: `animation.md`
(from animation-principles), `shot-design.md`, `shot-balance.md` and `shot-card.md` (from shot-design), and smaller
parts of `look.md` and `studio.md` (from look-and-light and directing-sessions). Ideas and thresholds in the code
come from it too: `qc`'s motion scans (`scripts/musicvideo/video/scans.py`, from render-checks) and colour-tag check
(from rendering), the review page's known issues and review marks (from review-page), and `analyze`'s drum hits
(`scripts/musicvideo/video/drums.py`, from song-timing). Each adapted file says so at its top. They were edited to fit
this plugin; the originals are not installed with it.

```text
MIT License

Copyright (c) 2026 Imaginative Prompting

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## 3D models (CC0 1.0, public domain; in `studio/assets/models/`)

Downloaded from Poly Pizza. CC0 does not require credit; it is given anyway.

| File | Title | Author | Page | Licence |
|---|---|---|---|---|
| `car-hatchback-kl.glb` | Car Hatchback | Kay Lousberg | https://poly.pizza/m/BG0KAhmGDt | CC0 1.0 |
| `suv-quaternius.glb` | SUV | Quaternius | https://poly.pizza/m/xsMtZhBkxL | CC0 1.0 |
| `car-quaternius-a.glb` | Car | Quaternius | https://poly.pizza/m/unqqkULtRU | CC0 1.0 |
| `car-quaternius-b.glb` | Car | Quaternius | https://poly.pizza/m/Cz6yDaUcM9 | CC0 1.0 |
| `desk-chair-kenney.glb` | Desk Chair | Kenney | https://poly.pizza/m/CKSz6PB1vO | CC0 1.0 |
| `office-chair-quaternius.glb` | Office Chair | Quaternius | https://poly.pizza/m/UfKvrZBK6C | CC0 1.0 |
| `desk-kenney.glb` | Desk | Kenney | https://poly.pizza/m/6PbVkqPzEU | CC0 1.0 |
| `desk-creativetrio.glb` | Desk | CreativeTrio | https://poly.pizza/m/YJyJam67hJ | CC0 1.0 |
| `monitor-creativetrio.glb` | Monitor | CreativeTrio | https://poly.pizza/m/PvSjEbz11k | CC0 1.0 |
| `business-man-quaternius.glb` | Business Man (rigged, 24 animations) | Quaternius | https://poly.pizza/m/JFrLIKqvCH | CC0 1.0 |
| `man-in-suit-quaternius.glb` | Man in Suit (rigged, 11 animations) | Quaternius | https://poly.pizza/m/mQnGoME1ez | CC0 1.0 |
| `animated-woman-quaternius.glb` | Animated Woman (rigged, 10 animations) | Quaternius | https://poly.pizza/m/9kF7eTDbhO | CC0 1.0 |
| `woman-headset-overscore.glb` | Woman wearing headset | overscore_media | https://poly.pizza/m/Qy6esq7e1z | CC0 1.0 |
| `business-dude-polygonal.glb` | Business Dude | Polygonal Mind | https://poly.pizza/m/odKDM2t8Cr | CC0 1.0 |

## Character avatars (CC0 1.0; downloaded by `doctor`, not shipped)

The `vrm` character engine uses the four VRoid β sample avatars (β Ver AvatarSample_1 to 4, by VRoid Project,
pixiv Inc.). pixiv waives copyright on them (CC0): https://vroid.pixiv.help/hc/en-us/articles/4402614652569. They
are not in this repo: `music-video doctor` (or `music-video avatars install`) downloads them into the install
folder, from the OpenGameArt CC0 mirror (https://opengameart.org/content/vroid-studio-cc0-models), and keeps a file
only when its sha256 matches the one pinned in `scripts/musicvideo/avatars.py`. The install folder's `SOURCES.md`
lists each one. AvatarSample_A, B and C have other terms and are never used.

## Fonts

- **Outfit** (SIL Open Font License 1.1), by The Outfit Project Authors: converted to a static typeface JSON in
  `studio/kit/three/fonts/outfit-800.json` for 3D text; the licence is in `studio/kit/three/fonts/OFL.txt`.
- Fonts a video loads through `@remotion/google-fonts` are Google Fonts (OFL or Apache 2.0) and are fetched at render
  time, not shipped.

## npm packages (installed by `doctor` into the install folder, not shipped)

- **three.js** (MIT), **React** (MIT), **@react-three/fiber** (MIT), **Vite** (MIT, builds the web page), and
  their dependencies under their own licences.
- **@pixiv/three-vrm** 3.5.5 (MIT, Copyright (c) 2019-2026 pixiv Inc.) and its `@pixiv/three-vrm-*` packages: VRM
  loading, MToon shading, spring bones, expressions and look-at for the `vrm` character engine. The kit's
  `kit/three/vrm/` follows its documented use; none of its code is copied into this repo.
- **perfect-freehand** 1.2.3 (MIT, Copyright (c) 2021 Stephen Ruiz Ltd, by Steve Ruiz): the brush strokes of the
  `cartoon` character engine (`kit/cartoon/ink.tsx`).
- **flubber** 0.4.2 (MIT, Copyright (c) 2017 Noah Veltman): the mouth and smear shape morphs of the `cartoon`
  engine (`kit/cartoon/rig.ts`). Its dependencies come under their own licences: d3-array and d3-polygon
  (BSD-3-Clause), earcut, svg-path-properties and topojson-client (ISC), svgpath (MIT).
  The kit's `kit/cartoon/` uses both packages through their documented functions; none of their code is copied
  into this repo. Both licences read:

  ```text
  Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
  documentation files (the "Software"), to deal in the Software without restriction, including without limitation
  the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
  to permit persons to whom the Software is furnished to do so, subject to the following conditions:

  The above copyright notice and this permission notice shall be included in all copies or substantial portions of
  the Software.

  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
  THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
  CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
  IN THE SOFTWARE.
  ```
- **Remotion** (`remotion`, `@remotion/*`, including `@remotion/player`, which a built web page ships): Remotion's
  own licence. Remotion is free for individuals and companies
  of up to 3 people; larger companies need a company licence from remotion.pro. The licence is between you and
  Remotion: see https://www.remotion.dev/license.

## Suno

Songs are made in your own Suno account; the terms for using them are Suno's and depend on your plan.
