import React from 'react';
import { useVideoConfig } from 'remotion';
import { safeRect } from './safe';

/** Positions children inside the title-safe area (and clear of platform buttons in 9:16). */
export const SafeArea: React.FC<{ children: React.ReactNode; style?: React.CSSProperties }> = ({ children, style }) => {
  const { width, height } = useVideoConfig();
  const r = safeRect(width, height);
  return <div style={{ position: 'absolute', left: r.x, top: r.y, width: r.width, height: r.height, ...style }}>{children}</div>;
};
