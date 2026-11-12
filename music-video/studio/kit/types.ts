import type React from 'react';

// The JSON written by music-video align (timing.json) and music-video analyze (analysis.json).
export type TimingWord = {
  i: number; text: string; start: number; end: number; conf: number; source: string; line: number; backing: boolean;
  /** Set by onsets: the first sound's kind, how sure the measurement was, and how far it moved the start (s). */
  sound?: 'fricative' | 'stop' | 'voiced'; onset_conf?: number; moved?: number;
};
export type TimingLine = {
  i: number; text: string; section: number; backing: boolean; start: number; end: number; words: [number, number];
};
export type TimingSection = {
  i: number; name: string; start: number | null; end: number | null; lines: [number, number] | null;
};
export type Timing = { version: 1; duration: number; words: TimingWord[]; lines: TimingLine[]; sections: TimingSection[] };

export type Section = { id: string; name: string; start: number; end: number; sung: boolean };
export type Energy = { rms: number[]; low: number[]; mid: number[]; high: number[] };
export type DrumKind = 'kick' | 'snare' | 'hat' | 'crash';
export type DrumHit = { t: number; kind: DrumKind; strength: number };
export type Analysis = {
  version: 1; duration: number; fps: number; tempo: number; beats: number[]; downbeats: number[];
  sections: Section[]; energy: Energy; hits: { t: number; strength: number }[];
  /** Drum hits (analyze, from 0.9): measured on the mix minus the vocal stem, or the mix; grid = beats' distance. */
  drums?: { source: 'mix minus vocals' | 'mix'; hits: DrumHit[]; grid: number | null };
};

export type SongData = { timing: Timing; analysis: Analysis };
export type SongProps = {
  data: SongData | null;
  /** Render this many frames per output frame (tools/blur.ts averages them into motion blur). Default 1. */
  subframes?: number;
};

/**
 * How a video's characters are animated, chosen at the look step (look.ts `characterEngine`, video.yaml
 * `characters:`): 'raw' (written from scratch in scene code) or 'vrm' (three-vrm avatars, `@mv/kit/three`).
 */
export type CharacterEngine = 'raw' | 'vrm';
/** The bake-off window in song seconds (a take's t = 0 is `from`), and where the hit lands, in seconds into it. */
export type BakeoffProps = { from: number; to: number; hit: number };
/** One engine's take in a bake-off (bakeoff.ts, written by `music-video bakeoff new`). */
export type BakeoffEntry = { engine: CharacterEngine; Component: React.FC<BakeoffProps> };
