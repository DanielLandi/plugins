import React from 'react';
import { useCurrentFrame } from 'remotion';
import { InkShapes } from './ink';
import { boilSeed } from './motion';
import { buildCharacter, type Character, type Pose } from './rig';

/**
 * One cartoon character in a pose, drawn in brush ink inside the scene's <svg>. The lines boil every `hold` frames
 * (2: drawn on twos); give each character its own `seed` so two characters do not boil in step.
 */
export const Cartoon: React.FC<{ character: Character; pose: Pose; seed?: number; hold?: number; boil?: number }> = ({
  character, pose, seed = 1, hold = 2, boil,
}) => {
  const frame = useCurrentFrame();
  return <InkShapes shapes={buildCharacter(character, pose)} seed={boilSeed(frame, hold, seed)} boil={boil} />;
};
