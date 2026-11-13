// Two original characters for the cartoon engine (drawn in code; no show's characters or look). A video writes its
// own `Character` data for its own cast: change the colours and proportions, keep the hat or the sprout, or neither.
import type { Character } from './rig';

/** A tall tangerine bean in a striped beanie. */
const bean: Character = {
  fill: '#ff9a3c', shade: '#e8742a', hi: '#ffd2a1', limb: '#ff9a3c', shoe: '#3b4bd8',
  rx: 108, ry: 138, pear: 0.12, legLen: 92, hipW: 44, limbW: 20, handR: 30,
  eyeRx: 30, eyeRy: 40, eyeGap: 40, eyeY: 0.3, cheek: '#ff6f61',
  hat: { fill: '#7b4fd6', band: '#ffd23f', pom: '#ffffff' },
};

/** A short round plum with a springy two-leaf sprout. */
const plum: Character = {
  fill: '#b682f0', shade: '#9560d8', hi: '#ead8ff', limb: '#b682f0', shoe: '#ff5d7a',
  rx: 96, ry: 96, pear: 0.06, legLen: 64, hipW: 36, limbW: 17, handR: 26,
  eyeRx: 26, eyeRy: 33, eyeGap: 34, eyeY: 0.2, cheek: '#ff7fb0',
  sprout: { stem: '#3f8f2e', leaf: '#6cd04f' },
};

export const cast = { bean, plum };
