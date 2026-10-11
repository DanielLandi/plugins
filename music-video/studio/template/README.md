# __ID__

Made with the music-video plugin.

## Credits

- Song: created with Suno, in the artist's own account.
- Video: code-rendered with Remotion (https://www.remotion.dev; see its licence terms).
- Transitions: remotion-transitions by GTKottman and contributors (MIT).
- Fonts and other assets: see SOURCES.md.

## Re-render

Ask Claude to re-render this video, or run these from the plugin (`paths __ID__` prints the folders):

    music-video render __ID__ __ID__-full <renders>/final-silent.mp4 --muted --crf=18
    music-video mux <renders>/final-silent.mp4 --spec __ID__ --out <deliver>/final.mp4
