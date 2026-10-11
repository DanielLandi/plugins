import React from 'react';
import { Html5Audio, staticFile } from 'remotion';

/** The song, for watching in the Studio. Final renders are --muted and music-video mux adds the untouched MP3. */
export const SongAudio: React.FC = () => <Html5Audio src={staticFile('song.mp3')} />;
