// The JSON written by music-video align (timing.json) and music-video analyze (analysis.json).
export type TimingWord = {
  i: number; text: string; start: number; end: number; conf: number; source: string; line: number; backing: boolean;
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
export type Analysis = {
  version: 1; duration: number; fps: number; tempo: number; beats: number[]; downbeats: number[];
  sections: Section[]; energy: Energy; hits: { t: number; strength: number }[];
};

export type SongData = { timing: Timing; analysis: Analysis };
export type SongProps = {
  data: SongData | null;
  /** Render this many frames per output frame (tools/blur.ts averages them into motion blur). Default 1. */
  subframes?: number;
};
