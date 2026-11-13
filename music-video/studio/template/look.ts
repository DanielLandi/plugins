import type { CharacterEngine, LyricMode, LyricStyle } from '@mv/kit';

// Written from LOOK.md once the look is approved (step 5). Fonts: load with @remotion/google-fonts/<Family>.
export const palette = { background: '#101418', neutral: '#d9dde3', neutral2: '#5a6270', accent: '#f5c542' };

/** Decided at step 6 by watching the sample with and without: 'none' | 'lines' | 'words'. */
export const subtitles: LyricMode = 'words';
/** The vertical cut is watched with the sound off: subtitles on unless the user says otherwise. */
export const verticalSubtitles: LyricMode = 'words';

/**
 * Step 5's jolts question: do things jolt on the beat (the camera kicking on the kick drum, a shake on hits)? true
 * only when the user said yes; unanswered means false. Keep `jolts:` in video.yaml the same (qc reads it there).
 */
export const jolts: boolean = false;

/**
 * Step 5's character engine, when the video has characters: 'raw' (drawn and moved from scratch in scene code),
 * 'vrm' (three-vrm anime avatars) or 'cartoon' (hand-inked 2D rubber-hose characters). null means no characters. Keep `characters:` in video.yaml and the
 * **Characters:** line of LOOK.md the same.
 */
export const characterEngine: CharacterEngine | null = null;

export const lyricStyle: LyricStyle = {
  fontFamily: 'Helvetica, Arial, sans-serif',
  size: 0.06,
  color: palette.neutral,
  highlight: palette.accent,
  position: 'bottom',
};
