import type { BakeoffEntry } from '@mv/kit';

// Rewritten by `music-video bakeoff new <id>`: the same short brief built once per character engine, each a
// composition <id>-bakeoff-<engine> over the same song window (index.tsx registers them); `hit` is where the song's
// strongest hit lands, in seconds into the window. Empty: no bake-off (`music-video bakeoff clear <id>` puts this back).
export const bakeoff: { from: number; to: number; hit: number; entries: BakeoffEntry[] } = { from: 0, to: 10, hit: 6, entries: [] };
