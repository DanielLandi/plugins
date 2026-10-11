import type { Analysis, Timing } from '@mv/kit';

const w = (i: number, text: string, start: number, end: number, line: number, backing = false) => ({
  i, text, start, end, conf: 0.9, source: 'align', line, backing,
});

export const fixtureTiming: Timing = {
  version: 1,
  duration: 4,
  words: [w(0, 'Rain', 0.4, 0.9, 0), w(1, 'on', 0.9, 1.1, 0), w(2, 'the', 1.1, 1.3, 0), w(3, 'road', 1.3, 2.0, 0),
    w(4, 'rain', 2.4, 3.0, 1, true)],
  lines: [
    { i: 0, text: 'Rain on the road', section: 0, backing: false, start: 0.4, end: 2.0, words: [0, 3] },
    { i: 1, text: '(rain)', section: 1, backing: true, start: 2.4, end: 3.0, words: [4, 4] },
  ],
  sections: [
    { i: 0, name: 'Verse', start: 0.4, end: 2.0, lines: [0, 0] },
    { i: 1, name: 'Chorus', start: 2.4, end: 3.0, lines: [1, 1] },
  ],
};

const flat = (v: number) => Array.from({ length: 120 }, () => v);

export const fixtureAnalysis: Analysis = {
  version: 1, duration: 4, fps: 30, tempo: 120,
  beats: [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5], downbeats: [0, 2],
  sections: [
    { id: 'verse', name: 'Verse', start: 0, end: 2.2, sung: true },
    { id: 'chorus', name: 'Chorus', start: 2.2, end: 4, sung: true },
  ],
  energy: { rms: flat(0.5), low: flat(0.4), mid: flat(0.3), high: flat(0.2) },
  hits: [{ t: 2.2, strength: 1 }],
};
