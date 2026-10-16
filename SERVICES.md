# External services

| Service | Used by | Key | Who pays |
|---|---|---|---|
| GitHub Actions | `.github/workflows/ci.yml` | none | free (public repo) |
| Suno (`suno.com`) | `music-video` skills | none: used only through the user's own signed-in Chrome via Claude in Chrome; no API | the user (their Suno plan) |
| npm registry, Remotion's headless-browser CDN, PyPI and the alignment models' hubs (first run) | `music-video` `doctor`, `align` | none | free |
| Poly Pizza (`poly.pizza`) | source of `music-video/studio/assets/models` (CC0), no runtime use | none | free |

The repo itself holds no keys.

`batatais` is an instruction-only plugin with no runtime service or API key. Its
workflow recommends public OpenStreetMap/Overpass queries and photographic research
(including Street View), and optional licensed textures from sources such as Poly
Haven. The user's agent makes those requests during a reconstruction; installation
only downloads the plugin from GitHub and does not contact those services.
