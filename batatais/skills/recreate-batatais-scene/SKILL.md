---
name: recreate-batatais-scene
description: Reconstruct the Igreja Matriz de Batatais, its gardens and surrounding streets in Blender from maps and photographic evidence, using reproducible Python scripts. Use for a new reconstruction or further architectural and rendering detail; not for installing Blender or downloading an existing model.
---

# Reconstruct Batatais in Blender

Create a new, scripted interpretation of the Igreja Matriz do Senhor Bom Jesus
da Cana Verde in Batatais, São Paulo, Brazil, its two praça blocks and nearby
shopfronts. The published examples are at
https://haik.world/models/batatais/about/.

This package contains a workflow, not the private Blender project, its generators,
source photographs, `.blend` files or model assets. Write the generation scripts
for the user's reconstruction. Do not promise an identical copy, measured accuracy,
a fixed object count or a particular build time.

## Establish the working scene

Inspect the project instructions and existing files first. For a fresh build,
create a dedicated output directory and start an empty scene. For an existing
scene, preserve unrelated collections and save a new version before rebuilding.
Locate the user's Blender executable; do not assume a macOS installation path.

Use background Blender for repeatable builds and renders, or an already configured
Blender MCP connection for interactive inspection. MCP is optional. Do not install
an addon or change the user's agent configuration as a side effect of generating
geometry. If an MCP connection is used, only one Blender instance should own its
port. Split long builds and renders into separate calls, and use background jobs
with logs for work exceeding tool timeouts.

A typical command, after writing the named script, is:

```sh
blender -b --factory-startup --python-exit-code 1 -P scripts/build.py
```

Use project-relative paths resolved from the script file, explicit output paths,
and deterministic random seeds. Save scripts, reference metadata, placement data
and a short rebuild command alongside the scene.

## Collect evidence before geometry

Use OpenStreetMap to anchor roads, blocks and building footprints. Fetch and retain
a dated snapshot through a public Overpass endpoint, respecting its limits. An
initial area to inspect is latitude -20.8945..-20.8895, longitude
-47.5875..-47.5815; check it on a map before treating it as the final extent.
Record the query, timestamp and coordinate transform.

Use internet photographs, municipal reference material and Street View observations
for elevations, colors, shop signs, planting and small architectural details.
Inspect the images themselves. Record source URLs, dates, viewing directions and
uncertainty. Distinguish a visible feature from a plausible inference. Heights,
hidden roofs, lot divisions and historical changes need explicit estimates.

For an independent reconstruction, use raw evidence instead of another model's
geometry, generators or derived placement data. A shared coordinate convention
is useful for comparison and does not require copying the other reconstruction.

Keep a source ledger with permissions and attribution. Observation of an image
does not grant permission to embed its pixels in a texture. Prefer suitable
licensed images, CC0 surface scans or newly generated artwork for distributed
assets. Preserve attribution and share-alike obligations where applicable.

## Coordinate convention

Work in metres, with the church footprint centroid near the origin. For comparison
with the published Batatais examples, use +x north and -y east. The church faces
east; its nave follows y. These approximate layout guides must be checked against
new evidence, not treated as a measured architectural survey:

| Feature | Starting guide |
|---|---|
| Church front / rear | y ≈ -31 / +33 |
| Church block, Praça da Matriz | x ≈ -56..52, y ≈ -38..75 |
| Garden, Praça Cônego Joaquim Alves | east of the church, y ≈ -39..-150 |
| Rua Celso Garcia / Rua da Andorama | north / south edges |
| Rua Maj. Antônio Cândido | between church and garden |
| Rua Dr. Alberto Gaspar Gomes | east of the garden |
| Rua Dr. Leandro Cavalcante | west of the church |

For a small local extent, project longitude and latitude into local north/east
metres around the chosen origin, then map north to x and east to -y. Check the
result against recognizable intersections before placing frontages.

## Build in reproducible passes

**The scripts are the model.** Every correction to geometry, materials or placement
belongs in code or its input data. Rebuilding must reproduce the correction.
A useful division is helper geometry/materials, church, site/frontages, rendering
and export; create only the modules the task needs.

- Start with road centerlines, sidewalks, both praça blocks, the church mass and
  frontage footprints. Inspect an overhead render before architectural detail.
- Build the nave, transept, apse, crossing dome, twin bell towers and east facade.
  Refine portals, engaged columns and capitals, cornices, niches, inscriptions,
  clocks, roof profiles, mosaic and stained glass using close references.
- Build the garden from observed paths and planting beds. Refine topiary,
  bandstand, fountains or ponds, benches, lamps, curbs and access points.
- Store frontage placement in structured data. Use a reusable lot builder with
  custom details per building. Revisit shop signs, awnings, shutters, windows,
  setbacks and rooflines. Locate Raytur from evidence instead of guessing its lot.

Use direct mesh construction or `bmesh` for repeated primitives. Avoid thousands
of context-dependent `bpy.ops` calls in loops. Share meshes or instance repeated
props where practical. Clean only objects owned by the generator; do not delete
unrelated scene content. Give collections and outputs stable names.

After each meaningful pass: rebuild, render a useful view, inspect the image,
compare with the reference and correct the script. Check the church, garden and
frontages separately as well as together. Save a recoverable checkpoint before
expensive detail work.

## Improve rendering deliberately

Keep a lightweight interactive scene and a separate quality scene when needed.
For more realistic images, work on silhouette and scale before adding complexity:
rounded architectural edges, recessed openings, varied leaf shapes, palm fronds,
grass clumps, believable roof caps and contact with the ground.

Use image-based PBR materials with appropriate physical scale, roughness and normal
maps. Match lighting direction to the intended time of day. Cycles can supply
indirect light and reflections; inspect sample renders before committing to long
jobs. Check denoising, color management, glass, shadow detail and exposure.
Procedural complexity alone does not make a reconstruction accurate or realistic.

For a camera tour, author a continuous path and target track, test low-resolution
keyframes and a preview, then render the agreed duration and resolution. Inspect
clearance through planting and buildings, motion speed, opening view and final
framing. A garden → church orbit → Raytur finish is one route, not a mandatory one.
Encode a browser-friendly MP4 with fast-start metadata and supply a poster.

## Export and verify

Run export against a saved copy in background Blender. Web glTF cannot preserve
all Blender procedural nodes: provide UVs and baked or image-based materials,
verify alpha and culling, and inspect the actual exported asset in a browser.
Group meshes by material and spatial tile to control draw calls; use compression
and texture-size limits appropriate to the target device. Avoid coplanar duplicate
surfaces. Retain required credits in the viewer and alongside rendered media.

Verify a clean rebuild, inspect final renders, and report the source evidence,
approximations, reproduction commands and output paths. If publishing is requested,
check the delivered pages, model loading, attribution and video seeking. Do not
publish private project files or observational captures as part of the recipe.
