import type { SceneEntry } from '@mv/kit';
import { Chorus } from './scenes/Chorus';
import { Verse } from './scenes/Verse';

export const scenes: SceneEntry[] = [{ id: 'verse', from: 0, Component: Verse }, { id: 'chorus', from: 2.2, Component: Chorus }];
