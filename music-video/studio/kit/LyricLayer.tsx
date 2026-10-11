import React, { useMemo } from 'react';
import { interpolateColors, useVideoConfig } from 'remotion';
import { lineAt, scheduleLines, wordProgress } from './lyrics';
import { safeRect } from './safe';
import { useSongData, useSongTime } from './SongContext';
import type { TimingLine } from './types';

export type LyricMode = 'none' | 'lines' | 'words';
export type LyricStyle = {
  fontFamily: string;
  fontWeight?: number;
  /** Font size as a fraction of the frame height. */
  size: number;
  color: string;
  /** The colour a word sweeps to while it is sung ('words' mode). */
  highlight: string;
  shadow?: string;
  position: 'top' | 'center' | 'bottom';
};

const FADE_S = 0.15;

/** Normalised line text, for matching a lyric line by its words (case, punctuation and spacing ignored). */
export const lineKey = (text: string) => text.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();

/**
 * Overlay subtitles. `hide` leaves out lines the picture already spells out (words drawn into the scene), so a line
 * is never written twice.
 */
export const LyricLayer: React.FC<{ mode: LyricMode; style: LyricStyle; hide?: (line: TimingLine) => boolean }> = ({
  mode, style, hide,
}) => {
  const { timing } = useSongData();
  const t = useSongTime();
  const { width, height } = useVideoConfig();
  const schedule = useMemo(() => scheduleLines(timing.lines), [timing]);
  if (mode === 'none') return null;
  const current = lineAt(schedule, t);
  if (!current || hide?.(current.line)) return null;
  const rect = safeRect(width, height);
  const opacity = Math.max(0, Math.min(1, (t - current.from) / FADE_S, (current.to - t) / FADE_S));
  const [a, b] = current.line.words;
  const justify = style.position === 'top' ? 'flex-start' : style.position === 'center' ? 'center' : 'flex-end';
  return (
    <div style={{ position: 'absolute', left: rect.x, top: rect.y, width: rect.width, height: rect.height, display: 'flex',
      flexDirection: 'column', justifyContent: justify, alignItems: 'center', opacity, pointerEvents: 'none' }}>
      <div style={{ fontFamily: style.fontFamily, fontWeight: style.fontWeight ?? 700, fontSize: style.size * height,
        lineHeight: 1.15, textAlign: 'center', textShadow: style.shadow ?? '0 2px 12px rgba(0,0,0,0.6)', maxWidth: '100%' }}>
        {timing.words.slice(a, b + 1).map((w) => {
          const color = mode === 'words' ? interpolateColors(wordProgress(w, t), [0, 1], [style.color, style.highlight]) : style.color;
          return (
            <span key={w.i} style={{ color, display: 'inline-block', marginRight: '0.28em',
              fontStyle: w.backing ? 'italic' : 'normal', fontSize: w.backing ? '0.8em' : '1em' }}>
              {w.text}
            </span>
          );
        })}
      </div>
    </div>
  );
};
