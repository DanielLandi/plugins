import type { BakeoffEntry } from '@mv/kit';

// Rewritten by `music-video bakeoff new <id>`: the same short brief built once per character engine, each a
// composition <id>-bakeoff-<engine> over the same song window (index.tsx registers them). Empty: no bake-off.
export const bakeoff: { from: number; to: number; entries: BakeoffEntry[] } = { from: 0, to: 10, entries: [] };
