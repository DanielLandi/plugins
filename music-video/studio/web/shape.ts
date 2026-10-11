/**
 * The composition size for a window: 1080 high, as wide as the window's shape, in even pixels. A window with no
 * area yet (a hidden tab, an iframe being laid out) gets 16:9; shapes beyond 3:1 either way are clamped, and the
 * player letterboxes the rest in the sky's colour.
 */
export const compositionSize = (w: number, h: number, height = 1080) => {
  const aspect = w > 0 && h > 0 ? Math.min(3, Math.max(1 / 3, w / h)) : 16 / 9;
  return { width: Math.max(2, Math.round((height * aspect) / 2) * 2), height };
};
