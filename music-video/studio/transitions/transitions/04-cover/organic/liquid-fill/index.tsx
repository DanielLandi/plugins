import React from 'react';
import { bridged, paramDefaults } from '../../../../src/core';
import meta from './transition.json';
import { LiquidFill, type LiquidOrigin } from './LiquidFill';

export { LiquidFill };

type P = { color: string; seed: number; rows: number; from: LiquidOrigin; gap: number; wobble: number; hold: number };

/** Liquid floods scene A, holds, then scene B floods back in through holes in it. */
export default bridged<P>(paramDefaults<P>(meta), ({ phase, progress, params: { hold: _h, ...p } }) =>
  phase === 'in' ? <LiquidFill {...p} progress={progress} /> : <LiquidFill {...p} seed={p.seed + 1} invert progress={progress} />,
);
