export type Layout = 'landscape' | 'portrait';

export const layoutOf = (width: number, height: number): Layout => (width >= height ? 'landscape' : 'portrait');

/** Margins as fractions of the frame. Portrait keeps clear of Shorts/Reels titles, captions and buttons. */
export const SAFE = {
  landscape: { top: 0.05, bottom: 0.05, left: 0.05, right: 0.05 },
  portrait: { top: 0.14, bottom: 0.22, left: 0.05, right: 0.12 },
} as const;

export const safeRect = (width: number, height: number) => {
  const m = SAFE[layoutOf(width, height)];
  return { x: width * m.left, y: height * m.top, width: width * (1 - m.left - m.right), height: height * (1 - m.top - m.bottom) };
};
