import type { SceneEntry } from '@mv/kit';
import { Placeholder } from './scenes/Placeholder';

// One entry per storyboard section, in order. `from` is the section's start in seconds (analysis.json sections,
// or a nearby downbeat). Each Component lives in scenes/<id>.tsx and is written by that section's scene agent.
export const scenes: SceneEntry[] = [{ id: 'all', from: 0, Component: Placeholder }];
