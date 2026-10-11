# A Taxonomy of Transitions in Motion Design

This document defines how every transition in this library is classified, named and filed.
It is the source of truth for the folder structure: each folder in `transitions/` is a **family**
defined here, and each folder inside it is a **subfamily** defined here. The machine-readable copy is
`taxonomy.json`; the two must always agree.

Contents

1. The model
2. The decision procedure (how to classify anything)
3. The nine families
4. Facets (how a transition looks, moves and feels)
5. Choosing a transition by intent
6. Timing and craft
7. Hybrids and worked classifications
8. Implementation in Remotion
9. Filing rules
10. Design rules for this library
11. Glossary

---

## 1. The model

A transition is the span of time in which the viewer stops watching **A** and starts watching **B**.
A and B can be shots, scenes, layouts, slides or states of one design.

Every transition can be described by answering three questions:

| Question | Answered by | Example (Liquid Fill) |
|---|---|---|
| **What carries the change?** | The **family** (one only) and its **subfamily** | Cover › Organic |
| **What shape does the change take?** | The **facets**: structure, origin, edge, layers, space, timing, tone | bridged, distributed, organic, third layer, 2D, eased, clean |
| **What does the change say?** | The **function** | section break |

The family is about **mechanism**, not appearance. Two transitions that look alike but work
differently belong to different families. For example, a white flash with bloom is *Light*,
while a flat fade to white is *Blend*. Two transitions that look very different but work the
same way share a family: a liquid fill and a sliding solid panel are both *Cover*.

The family is chosen by what the **viewer perceives** as the main mechanic, not by how it was
built. A wipe made in a 3D package is still a Wipe.

---

## 2. The decision procedure

Ask these questions **in order** and stop at the first "yes". The order matters: it
resolves the overlaps between families. For example, a light leak covers the frame, but
question 4 catches it before question 5 does.

| # | Question | If yes → |
|---|---|---|
| 1 | Are there **zero in-between frames**? A changes to B from one frame to the next. | **01 Cut** |
| 2 | Does a **specific element keep its identity** and lead the eye from A into B? | **08 Carry** |
| 3 | Does an element in A **turn into** a different element in B, with in-between frames? | **07 Morph** |
| 4 | Is the in-between made of **light**: glow, flare, burn, leak, or a flash with bloom? | **09 Light** |
| 5 | Does a **third layer** (colour, graphic, texture) cover most or all of the frame between A and B? | **04 Cover** |
| 6 | Does the picture **move rigidly** (translate, rotate, scale, flip), as a whole or in slices? | **05 Motion** |
| 7 | Is the picture **deformed, degraded or broken apart**? | **06 Distortion** |
| 8 | Does a **moving boundary** separate A from B, with a mask that is *designed* (not taken from the footage)? | **03 Wipe** |
| 9 | Otherwise, A and B **mix by opacity**, possibly through a flat colour or a luminance key. | **02 Blend** |

Tie-breakers:

- **Rigid vs non-rigid.** If pixels keep their shape while they move, it is Motion (6). If they bend, smear, tear or scatter, it is Distortion (7).
- **Designed mask vs footage mask.** If the reveal shape comes from the image's own brightness, it is Blend › Luma Dissolve. If it comes from a designed shape, gradient or texture, it is Wipe.
- **Element identity.** If the element stays the same thing and leads you in, it is Carry. If it becomes another thing, it is Morph. If it is a big shape that only blocks the view, it is Cover.
- **Full coverage.** A Cover hides A completely, or almost completely, at its peak. If A and B are always both visible on either side of an edge, it is a Wipe.

If two families still seem equally right, file the transition under the one whose question
comes **first** in the table, and record the other one in the `also` facet.

---

## 3. The nine families

Each family below gives a definition, a membership test, its subfamilies, its boundaries with
neighbouring families, typical use, and how to build it.

### 01 Cut

**Definition.** A changes to B between two consecutive frames, with no in-between frames.
The craft is entirely in *what* is cut to and *when*.

**Test.** Step through the change frame by frame. If no frame contains a mix of A and B, it is a Cut.

| Subfamily | What it is | Examples |
|---|---|---|
| **Match Cut** | A and B share a form, motion, colour or composition, so the eye carries across | circle → moon, door slam → gavel, a pan that continues |
| **Smash Cut** | An abrupt jump in tone, volume or energy, used for contrast or comedy | silence → loud party, calm → chaos |
| **Jump Cut** | The same subject with a jump in time, which compresses time or adds energy | vlog cuts, a montage of a drawing appearing |
| **Audio-Led** | Sound changes before or after the picture (J-cut, L-cut), or a sound hit drives the cut | B's audio starts under A, a whoosh into a hard cut |

**Boundaries.** A cut with motion blur added is Motion › Whip. A cut hidden under a flash is Light › Flash.

**Function.** Continuity, contrast, energy. The cut is the default transition: everything else needs a reason.

**Build.** No presentation needed; place two sequences end to end. A Cut folder holds guides and
reference rather than overlays.

### 02 Blend

**Definition.** A and B mix by opacity. Nothing moves and no edge travels across the frame.

**Test.** Is every pixel a weighted mix of A and B (or of a flat colour), with no boundary moving across the frame?

| Subfamily | What it is | Examples |
|---|---|---|
| **Crossfade** | A fades out while B fades in | standard dissolve, slow dissolve for time passing |
| **Dip to Colour** | A fades to a flat colour, then B fades in from it | dip to black, dip to white, dip to brand colour |
| **Luma Dissolve** | The image's own brightness decides which pixels change first | highlights dissolve first, shadows last |
| **Blend Mode** | The mix uses a blend mode instead of normal opacity | additive "film" dissolve, multiply, difference |

**Boundaries.** A dip to white with glow or bloom is Light › Flash. A dissolve through a designed texture map is Wipe › Organic or Wipe › Pattern.

**Function.** Progression (time passes), softness, continuity. Long dissolves read as memory or dream.

**Build.** Remotion built-in `fade()`. Dip to Colour is a Cover-style bridged structure with a flat
layer, but it stays in Blend because the viewer sees only an opacity change.

### 03 Wipe

**Definition.** A moving boundary separates A from B. On one side of the edge you see A, on the
other side B. The shape of the boundary is designed.

**Test.** Is there a visible edge with A on one side and B on the other, and does that edge travel until B fills the frame?

| Subfamily | What it is | Examples |
|---|---|---|
| **Linear** | A straight edge sweeps across | left-to-right, diagonal, soft-edge gradient wipe |
| **Iris** | A circle or shape grows from (or shrinks to) a point | iris in or out, keyhole, cartoon "that's all folks" |
| **Clock** | An edge rotates around a centre | clock wipe, radar sweep, pie wipe |
| **Shape Mask** | B appears through a growing designed shape | logo reveal, letterform mask, star, heart |
| **Pattern** | Many small edges at once, in a grid or repeat | blinds, checkerboard, venetian, halftone dots, stripes |
| **Organic** | The edge is irregular or noise-driven, and there is no full cover | ink-edge wipe, burn-edge without light, liquid edge straight to B |

**Boundaries.** If a coloured layer fills the screen between A and B, it is Cover. If the slices of
A *move away*, it is Motion › Split. If the mask comes from footage brightness, it is Blend › Luma Dissolve.

**Function.** Progression, a change of place, playful or retro energy (wipes read as "deliberate",
iris reads as cartoon or vintage).

**Build.** Remotion built-ins: `wipe()` (Linear), `clockWipe()` (Clock), `iris()` (Iris). Anything
else is a direct mask presentation: render B inside a mask whose shape is driven by progress.

### 04 Cover

**Definition.** A third layer that is neither A nor B covers the frame, hides the change, then
uncovers B. At its peak the viewer sees only the cover.

**Test.** Pause at the middle of the transition. Is the frame mostly or entirely a layer that is neither A nor B?

| Subfamily | What it is | Examples |
|---|---|---|
| **Organic** | The cover is a fluid, natural or noise-driven substance | liquid fill, ink bleed, paint splat, smoke fill, reaction-diffusion |
| **Geometric** | The cover is built from clean shapes | shape burst, grid of circles or squares scaling up, hexagon fill |
| **Stroke** | One or more drawn strokes sweep and fill the frame | brush stroke, marker swipe, ribbon, swoosh lines |
| **Panel** | Solid slabs slide or unfold across and then off | curtain, sliding colour bars, stacked panels |
| **Stinger** | A branded or character-driven graphic covers the cut | logo stinger, mascot run-across, esports stinger |

**Boundaries.** A cover made of light is Light. A cover that is simply a flat colour faded in by
opacity is Blend › Dip to Colour. A shape that grows *and reveals B inside itself* with no cover
phase is Wipe › Shape Mask.

**Function.** Section breaks, brand moments, hiding a hard edit, energy. Cover is the workhorse of
motion-design transitions because it hides any cut, whatever A and B are.

**Build.** Bridged structure: *cover* (third layer grows over A) → *hold* (fully covered, cut
happens) → *reveal* (third layer opens to show B). In code, the reveal half is the same shape
rendered inverted, so one engine serves both halves (see section 8).

### 05 Motion

**Definition.** The picture moves rigidly. A and B translate, rotate, scale or flip as whole
frames or as rigid slices, as if the camera or the canvas moved.

**Test.** Do the pixels keep their shape while they move?

| Subfamily | What it is | Examples |
|---|---|---|
| **Push Slide** | B pushes A out, or slides over it | push left, slide up, card stack |
| **Whip** | A very fast move with motion blur that hides the seam | whip pan, whip tilt, whip zoom |
| **Zoom** | Scale through the frame | zoom-through, punch-in, zoom-out reveal |
| **Spin** | Rotation in the picture plane | spin, roll, rotate-and-scale |
| **3D Space** | Rigid 3D moves of the frame | flip, cube, fold, page turn, door |
| **Split** | The frame divides into rigid slices that move apart or together | split-screen slide, slats sliding away, shutter halves |

**Boundaries.** Slices that bend, shatter or smear are Distortion › Break. A zoom into an element
that contains B is Carry › Portal.

**Function.** Continuity of space ("we moved"), energy, direction (left/right implies forward/back).

**Build.** Remotion built-ins: `slide()` (Push Slide), `flip()` (3D Space). Others animate
transforms on A and B with a shared easing curve; add motion blur for Whip.

### 06 Distortion

**Definition.** The image itself deforms, degrades or breaks apart, and B emerges from the damage.

**Test.** Do the pixels bend, smear, glitch, pixelate or scatter?

| Subfamily | What it is | Examples |
|---|---|---|
| **Glitch** | Digital corruption | RGB split, datamosh, block displacement, scanline tear |
| **Warp** | Smooth non-rigid deformation | ripple, swirl, displacement map, liquify, heat haze |
| **Blur** | Focus or directional blur peaks at the cut | defocus, zoom blur, directional blur (without whole-frame motion) |
| **Pixel** | The image breaks into a grid of pixels or sorted pixels | pixelate, mosaic, pixel sort, dither dissolve |
| **Break** | The image fractures into pieces or particles | shatter, paper tear, crumble, disintegrate into particles |

**Boundaries.** Rigid slices = Motion › Split. A blur caused by a whole-frame move = Motion › Whip.
Glitch used as a brief overlay on a cut still belongs here.

**Function.** Energy, tension, tech or retro tone, "something went wrong", music-video beats.

**Build.** Usually a shader or `<canvas>` pass over A and B. The distortion amount peaks at the
midpoint, where the source swaps from A to B.

### 07 Morph

**Definition.** An element in A changes, through in-between frames, into a different element in B.

**Test.** Is there an element that is visibly one thing at the start and another thing at the end?

| Subfamily | What it is | Examples |
|---|---|---|
| **Shape** | One vector shape interpolates into another | circle → square, icon → icon |
| **Type** | Letters or words change into other letters, words or shapes | word swap, letter → logo |
| **Object** | A depicted object becomes another object | cup → planet, hand → bird |
| **Image Morph** | Whole images warp into each other via corresponding points | face morph, landscape → landscape |

**Boundaries.** With no in-between frames it is Cut › Match Cut. If the element keeps its identity
and leads the eye, it is Carry.

**Function.** Continuity of idea ("this *is* that"), explanation, cleverness. A favourite in explainers.

**Build.** Path interpolation (`@remotion/paths`: `interpolatePath`), shared layout positions, or a
mesh warp for Image Morph. These need knowledge of both scenes, so they are built inside the scene
code rather than as a generic presentation.

### 08 Carry

**Definition.** A specific element keeps its identity and **leads** the viewer from A into B.
The element is the protagonist; the change of scene is a consequence of following it.

**Test.** Is there an element that the eye follows from A into B, staying the same thing throughout?

| Subfamily | What it is | Examples |
|---|---|---|
| **Object-Led** | An object travels across and becomes part of B's layout | a ball rolls into the next scene, a product slides into place |
| **Line-Led** | A drawn line, path or connector travels and becomes B's structure | a line becomes a chart axis, a path becomes a map route |
| **Type-Led** | A word or title stays on screen and the scene rebuilds around it | the headline stays as the background changes, a word grows to fill the screen |
| **Portal** | The camera moves into an element that contains B | zoom into a screen, a window, a letter's counter, an eye |

**Boundaries.** If the element changes identity, it is Morph. If the camera simply moves and no
element leads, it is Motion. If a big element only blocks the view, it is Cover.

**Function.** Continuity, narrative flow, "one continuous take" design. This family is the
signature of high-end motion design, because the seams disappear.

**Build.** Like Morph, it needs both scenes: one shared element animates across a sequence
boundary, or A and B are built as one composition.

### 09 Light

**Definition.** Light washes over the cut: the in-between is luminance, glow or optical artefact.

**Test.** Does the frame get brighter, glowing or flared at the cut, with an optical (not flat) quality?

| Subfamily | What it is | Examples |
|---|---|---|
| **Flash** | A short burst of bright exposure with bloom | white flash, camera flash, colour flash |
| **Leak** | Soft coloured light drifts across | light leak, sun leak, prism leak |
| **Burn** | Film or paper burns through to white or to B | film burn, celluloid melt, burn-through |
| **Flare** | A lens flare or light streak sweeps across and hides the seam | anamorphic flare sweep, light streak |

**Boundaries.** A flat fade to white with no bloom is Blend › Dip to Colour. A burn-edge wipe with
no glow is Wipe › Organic.

**Function.** Energy, warmth, nostalgia (leaks and burns), impact (flashes on beats).

**Build.** Additive (screen or plus-lighter) layers over A and B, with the swap at peak brightness.
Stock footage overlays are common; generated ones can come from a shader.

---

## 4. Facets

Facets describe a transition within its family. Each transition records one value per facet,
using **only the vocabulary below**, so that the library stays searchable.

| Facet | Values | Meaning |
|---|---|---|
| `structure` | `direct` · `bridged` · `continuous` · `instant` | direct: A→B. bridged: A→third layer→B. continuous: no seam (Morph, Carry). instant: Cut. |
| `origin` | `edge-left` · `edge-right` · `edge-top` · `edge-bottom` · `edge-diagonal` · `point` · `edges-inward` · `path` · `distributed` · `whole-frame` | where the change starts |
| `edge` | `none` · `hard` · `soft` · `geometric` · `organic` · `textured` | character of the boundary |
| `layers` | `A` · `B` · `A+B` · `third` | which layers animate |
| `space` | `2d` · `2.5d` · `3d` | dimensionality |
| `timing` | `snap` · `eased` · `linear` · `elastic` · `beat-synced` | feel of the motion curve |
| `duration` | frame count at 30 fps, or a range | typical length |
| `tone` | `clean` · `playful` · `bold` · `luxe` · `gritty` · `technical` · `retro` · `dreamy` | mood |
| `function` | `continuity` · `progression` · `contrast` · `section-break` · `reveal` · `brand` · `energy` | what it tells the viewer (one or more) |
| `also` | any other family | secondary mechanic, for hybrids |

---

## 5. Choosing a transition by intent

Start from what the edit needs to say, then pick the family.

| You want to say… | Reach for | Avoid |
|---|---|---|
| "Same place, same moment" (continuity) | Cut, Match Cut, Carry, Motion › Push | long Blends and Covers, which imply time passed |
| "Time has passed" (progression) | Blend › Crossfade, Dip to Colour, slow Wipe | snappy Motion |
| "New chapter" (section break) | Cover, Wipe › Shape Mask, Dip to Colour | invisible transitions; the break should be felt |
| "Look at this" (reveal) | Wipe › Iris / Shape Mask, Carry › Portal, Cover reveal half | Glitch (it pulls focus) |
| "Jolt" (contrast) | Smash Cut, Flash, Glitch | slow Blends |
| "This is us" (brand) | Cover › Stinger, Shape Mask with the logo, brand-colour Cover | generic built-ins |
| "Keep the energy up" | Whip, Glitch, Flash on the beat, Geometric Cover | long dissolves |
| "It's all connected" (explainers) | Morph, Carry › Line-Led | Covers that hide the logic |

House-style rule: a piece should use **one or two families** for most of its transitions, and save a
different family for the moments that matter. Mixing many families reads as amateur.

---

## 6. Timing and craft

**Durations at 30 fps** (double at 60 fps):

| Kind | Typical length |
|---|---|
| Cut | 0 frames |
| Snappy Motion, Whip, Glitch, Flash | 6–12 frames |
| Standard Wipe, Push, Crossfade | 12–20 frames |
| Bridged Cover (cover + hold + reveal) | 36–72 frames in total; hold 4–12 frames |
| Hero moments, slow Blends | 45–90 frames |

**Easing.** Motion and Wipes should ease in and out. Ease-in-out cubic or quint is the default, and
an exponential ease-in-out suits snappy moves. Linear timing looks mechanical unless the design
calls for it. Organic Covers can grow fast and settle slowly (ease-out per element) while the
whole ends on time.

**The swap point.** Change from A to B at the moment of greatest coverage, blur, brightness or
speed: the midpoint of a Cover's hold, the blur peak of a Whip, the white peak of a Flash.

**Direction has meaning.** Left→right and bottom→top read as forward. Right→left and top→bottom read
as back or down. Keep directions consistent within a piece.

**Sound.** Most motion-design transitions are paired with a sound: a whoosh for Motion and Wipe, a
riser into a Cover, a hit at the swap point, a glitch burst for Distortion. Sync the hit to the swap frame.

**Motion blur.** Fast rigid moves need motion blur, or they strobe. In Remotion, use
`@remotion/motion-blur` or render directional blur in a shader.

**Safe frames.** A Cover's hold must be truly full (every pixel covered), or the cut shows.
Test the hold frames by measuring coverage, not by eye.

---

## 7. Hybrids and worked classifications

Most real transitions mix mechanics. File by the decision procedure (section 2) and record the
rest in `also`.

| Transition | Family › Subfamily | Why | also |
|---|---|---|---|
| Liquid fill (black over white, then white over black) | Cover › Organic | a third layer fills the frame at the peak | — |
| Liquid edge revealing B directly | Wipe › Organic | no full cover; A and B meet at the edge | Cover |
| Ink bleed from one point | Cover › Organic | the ink is a third layer | — |
| Shape grid scaling up from a corner | Cover › Geometric | squares cover the frame, then open | Wipe › Pattern |
| Venetian blinds | Wipe › Pattern | slats are masks; A doesn't move | — |
| Slats of A sliding off | Motion › Split | the slices move rigidly | — |
| Paper tear | Distortion › Break | A rips (non-rigid) | Wipe › Organic |
| Whip pan | Motion › Whip | rigid move + blur | Distortion › Blur |
| Zoom into a phone screen into the next scene | Carry › Portal | the screen leads the eye in | Motion › Zoom |
| Logo spins and fills the screen with brand colour | Cover › Stinger | the logo becomes a covering layer | Motion › Spin |
| Circle in A becomes the sun in B | Morph › Shape | identity changes | — |
| Circle travels and becomes a chart dot in B | Carry › Object-Led | identity kept, leads the eye | — |
| Fade to white with bloom on a drop | Light › Flash | luminance with optical glow | Blend |
| Flat fade to black | Blend › Dip to Colour | opacity only | — |
| Pixelate out, pixelate in | Distortion › Pixel | the image degrades | — |
| Light leak over a cut | Light › Leak | additive light hides the seam | — |
| Cut to the same framing a second later | Cut › Jump Cut | no in-between frames | — |

---

## 8. Implementation in Remotion

The `structure` facet decides the code pattern:

| Structure | Pattern | Built-ins |
|---|---|---|
| `instant` | two `<Sequence>`s end to end; no presentation | — |
| `direct` | a `TransitionSeries` presentation that renders B inside a mask (or moves A and B) | `fade`, `slide`, `wipe`, `flip`, `clockWipe`, `iris` |
| `bridged` | cover / hold / reveal: one shape engine draws the cover over A, then the same engine draws it **inverted** over B so B appears through holes | see `transitions/04-cover/organic/liquid-fill` |
| `continuous` | not a generic presentation: shared elements across scenes, or A and B built as one composition | `@remotion/paths` for Morph |

**Use a built-in when one fits**, and build custom only for what the built-ins can't do.

**Deliverables.** A transition is code plus metadata: `transition.json`, `index.tsx` and any helper
files. Media (previews, posters, alpha overlays) are **rendered from the code** and published as
release assets, never committed. See CONTRIBUTING.md and docs/CATALOG.md.

---

## 9. Filing rules

1. **Classify** the transition with the decision procedure (section 2). Write down the family, subfamily and every facet.
2. **File** it at `transitions/<family>/<subfamily>/<id>/`, where `<id>` is lowercase words joined by hyphens and names what it looks like (`liquid-fill`, `grid-zoom`). The id must not contradict the family: don't call a Cover a "wipe".
3. **Describe** it in `transition.json`. The facet values must use the controlled vocabulary in section 4 (enforced by `npm run validate`).
4. **Generate** the READMEs and the catalog with `npm run build`. Never edit generated files by hand.
5. **One home only.** Never copy a transition into a second family folder. Record secondary mechanics in `also`.
6. **New subfamily?** Only add one when at least two real transitions need it and none of the existing subfamilies fit. Add it to this document and `taxonomy.json` first (definition, test, examples).
7. **New family?** Do not add one lightly: the nine families cover the mechanics of the medium. If a transition truly fails every question in section 2, propose it in an issue first.

---

## 10. Design rules for this library

The taxonomy describes every kind of transition. The library only accepts ones that follow these rules.

1. **Motivate the change.** The new scene's look, and above all its background colour, must arrive
   through something on screen: a shape that grows, a cover in the new colour, a moving edge, a line,
   a light. Never swap the background behind a blur or a flash for no reason. Spin into an orange
   square that becomes the orange background; don't spin the whole frame and cut. Transitions that
   bring in a colour take a `color` parameter meaning "the incoming scene's background colour".
2. **No dated gimmicks.** No whole-frame 3D flips, cubes or page curls, no venetian blinds or
   checkerboards, no clock wipes, no star or heart irises, no shattering glass. If it looks like a
   default slideshow or early-2000s video-editor transition, it doesn't go in. Those still exist in
   the taxonomy (section 7 classifies them), because a classification has to cover everything.
3. **Ease everything.** Use the easing from `src/core` (in-out cubic or quint by default). Linear
   motion is only for deliberate mechanical looks.
4. **Hide the swap.** The frame where scene A becomes scene B must be covered, blurred, at peak
   speed or fully matched (section 6, "The swap point").
5. **Deterministic.** The same props must give the same frames on any machine: no `Math.random`,
   no clocks; use `rand()` from `src/core` with a seed.

---

## 11. Glossary

- **A / B.** The outgoing and incoming shot, scene or state.
- **Bridged.** A transition that passes through a third state (a cover) between A and B.
- **Cover / hold / reveal.** The three phases of a bridged transition.
- **Swap point.** The frame at which the underlying content changes from A to B.
- **Mask.** A shape that decides which pixels show B.
- **Luma.** Brightness of the image; a luma key uses it as a mask.
- **Rigid.** A move in which pixels keep their shape and relative positions.
- **Stinger.** A short branded animation used to cover a cut.
- **J-cut / L-cut.** Edits in which the audio of B starts before the picture (J) or the audio of A continues after it (L).
- **Alpha.** The transparency channel; overlays with alpha can be stacked over any footage.
