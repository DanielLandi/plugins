import React from 'react';
import { Compositions } from './fixture';

// The engine's own root renders only the fixture (unit smoke). User videos are rendered through the entry file
// that music-video writes for each video (<runtime>/.entries/<id>/index.ts).
export const Root: React.FC = () => <Compositions />;
