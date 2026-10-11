export type SceneSpec = { id: string; from: number };
export type CutSpec = {
  from: string; to: string; carrier: string; why: string; landsOn: string;
  transition: string; params?: Record<string, unknown>; frames: number;
};
export type SceneSlot = { id: string; durationInFrames: number; startFrame: number };
export type CutSlot = { cut: CutSpec; startFrame: number };
export type SeriesLayout = { scenes: SceneSlot[]; cuts: CutSlot[]; totalFrames: number };

/** Cut lengths (`CutSpec.frames`) are written at this rate: a beat is 30 × 60 / tempo frames. */
const BASE_FPS = 30;

/**
 * Frame layout for <TransitionSeries>: each scene runs from its `from` to the next scene's, lengthened by half of
 * each neighbouring cut, so every cut is centred on its boundary and the whole video stays exactly the song's length.
 * At a sub-frame rate (a multiple of 30 fps, for motion blur) cuts keep their length in time, and boundaries are
 * rounded at 30 fps first, so the blurred render cuts exactly where the sharp one does.
 */
export const layoutSeries = (
  scenes: readonly SceneSpec[], specs: readonly CutSpec[], durationS: number, fps: number,
): SeriesLayout => {
  const k = Math.max(1, Math.round(fps / BASE_FPS));
  const cuts = specs.map((c) => ({ ...c, frames: c.frames * k }));
  if (!scenes.length) throw new Error('No scenes: add at least one to scenes.ts');
  if (scenes[0].from !== 0) throw new Error(`The first scene must start at 0 s, not ${scenes[0].from}`);
  const totalFrames = Math.ceil(durationS * fps);
  const bounds = scenes.map((s) => Math.round(s.from * BASE_FPS) * k).concat(totalFrames);
  for (let i = 0; i < scenes.length; i++) {
    if (bounds[i + 1] <= bounds[i]) {
      const culprit = i + 1 < scenes.length ? scenes[i + 1].id : scenes[i].id;
      throw new Error(`Scene "${culprit}" has no length: scenes must start in order and before the song ends`);
    }
  }
  const between = scenes.slice(1).map((s, i) => {
    const found = cuts.find((c) => c.from === scenes[i].id && c.to === s.id);
    if (!found) throw new Error(`No cut from "${scenes[i].id}" to "${s.id}" in cuts.ts`);
    if (!(found.frames > 0)) throw new Error(`Cut ${found.from} → ${found.to} needs a positive frame count`);
    return found;
  });
  const stray = cuts.filter((c) => !between.includes(c));
  if (stray.length) {
    throw new Error(`cuts.ts has cuts between scenes that are not neighbours: ${stray.map((c) => `${c.from} → ${c.to}`).join(', ')}`);
  }
  const sceneSlots = scenes.map((s, i) => {
    const left = i > 0 ? between[i - 1].frames - Math.floor(between[i - 1].frames / 2) : 0;
    const right = i < between.length ? Math.floor(between[i].frames / 2) : 0;
    return { id: s.id, durationInFrames: bounds[i + 1] - bounds[i] + left + right, startFrame: bounds[i] - left };
  });
  between.forEach((c, i) => {
    const shortest = Math.min(sceneSlots[i].durationInFrames, sceneSlots[i + 1].durationInFrames);
    if (c.frames >= shortest) {
      throw new Error(`Cut ${c.from} → ${c.to} (${c.frames} frames) is longer than a scene it joins (${shortest} frames)`);
    }
  });
  return { scenes: sceneSlots, cuts: between.map((c, i) => ({ cut: c, startFrame: sceneSlots[i + 1].startFrame })), totalFrames };
};
