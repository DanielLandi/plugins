// Pixel checks for the transition board: the screen never goes blank, white, or flooded with a foreign colour.
export type Rgba = { data: Uint8Array; width: number; height: number };
export type Verdict = { ok: boolean; reason: string };

const luma = (r: number, g: number, b: number) => 0.2126 * r + 0.7152 * g + 0.0722 * b;
const pixels = (img: Rgba) => img.width * img.height;

export const lumaStats = (img: Rgba) => {
  let sum = 0;
  let sum2 = 0;
  for (let i = 0; i < pixels(img); i++) {
    const y = luma(img.data[i * 4], img.data[i * 4 + 1], img.data[i * 4 + 2]);
    sum += y;
    sum2 += y * y;
  }
  const mean = sum / pixels(img);
  return { mean, std: Math.sqrt(Math.max(0, sum2 / pixels(img) - mean * mean)) };
};

export const brightShare = (img: Rgba, min = 245) => {
  let n = 0;
  for (let i = 0; i < pixels(img); i++) if (luma(img.data[i * 4], img.data[i * 4 + 1], img.data[i * 4 + 2]) >= min) n++;
  return n / pixels(img);
};

export const dominant = (img: Rgba) => {
  const counts = new Map<number, number>();
  for (let i = 0; i < pixels(img); i++) {
    const key = ((img.data[i * 4] >> 5) << 6) | ((img.data[i * 4 + 1] >> 5) << 3) | (img.data[i * 4 + 2] >> 5);
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  let best = 0;
  let bestCount = 0;
  for (const [key, count] of counts) if (count > bestCount) [best, bestCount] = [key, count];
  const center = (v: number) => (v << 5) + 16;
  const color: [number, number, number] = [center(best >> 6), center((best >> 3) & 7), center(best & 7)];
  return { color, share: bestCount / pixels(img) };
};

export const shareNear = (img: Rgba, color: readonly number[], tol = 24) => {
  let n = 0;
  for (let i = 0; i < pixels(img); i++) {
    const d = Math.max(Math.abs(img.data[i * 4] - color[0]), Math.abs(img.data[i * 4 + 1] - color[1]), Math.abs(img.data[i * 4 + 2] - color[2]));
    if (d <= tol) n++;
  }
  return n / pixels(img);
};

const hex = (c: readonly number[]) => `#${c.map((v) => Math.min(255, v).toString(16).padStart(2, '0')).join('')}`;

/** frame: an in-between frame of a cut; a and b: the last frame before and the first after it. */
export const judgeFrame = (frame: Rgba, a: Rgba, b: Rgba): Verdict => {
  if (brightShare(frame) >= 0.85) return { ok: false, reason: 'blown out to white' };
  const { std } = lumaStats(frame);
  if (std < 3 && !(lumaStats(a).std < 3 && lumaStats(b).std < 3)) return { ok: false, reason: `flat frame (luma std ${std.toFixed(1)})` };
  const d = dominant(frame);
  if (d.share >= 0.85 && shareNear(a, d.color, 40) < 0.3 && shareNear(b, d.color, 40) < 0.3) {
    return { ok: false, reason: `flooded with ${hex(d.color)}, a colour neither scene has` };
  }
  return { ok: true, reason: 'ok' };
};

export const downscale = (img: Rgba, width: number, height: number): Rgba => {
  const data = new Uint8Array(width * height * 4);
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const sx = Math.min(img.width - 1, Math.floor((x * img.width) / width));
      const sy = Math.min(img.height - 1, Math.floor((y * img.height) / height));
      data.set(img.data.subarray((sy * img.width + sx) * 4, (sy * img.width + sx) * 4 + 4), (y * width + x) * 4);
    }
  }
  return { data, width, height };
};

export const hstack = (imgs: readonly Rgba[], gap = 8): Rgba => {
  const height = Math.max(...imgs.map((i) => i.height));
  const width = imgs.reduce((w, i) => w + i.width, 0) + gap * (imgs.length - 1);
  const data = new Uint8Array(width * height * 4);
  for (let i = 0; i < width * height; i++) data.set([16, 20, 24, 255], i * 4);
  let left = 0;
  for (const img of imgs) {
    for (let y = 0; y < img.height; y++) data.set(img.data.subarray(y * img.width * 4, (y + 1) * img.width * 4), (y * width + left) * 4);
    left += img.width + gap;
  }
  return { data, width, height };
};
