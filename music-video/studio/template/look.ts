import type { LyricMode, LyricStyle } from '@mv/kit';

// Written from LOOK.md once the look is approved (step 5). Fonts: load with @remotion/google-fonts/<Family>.
export const palette = { background: '#101418', neutral: '#d9dde3', neutral2: '#5a6270', accent: '#f5c542' };

/** Decided at step 6 by watching the sample with and without: 'none' | 'lines' | 'words'. */
export const subtitles: LyricMode = 'words';
/** The vertical cut is watched with the sound off: subtitles on unless the user says otherwise. */
export const verticalSubtitles: LyricMode = 'words';

export const lyricStyle: LyricStyle = {
  fontFamily: 'Helvetica, Arial, sans-serif',
  size: 0.06,
  color: palette.neutral,
  highlight: palette.accent,
  position: 'bottom',
};
