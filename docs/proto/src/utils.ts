/** Remap a value from [inMin, inMax] to [0, 1], clamped. */
export function remap(value: number, inMin: number, inMax: number): number {
  return Math.max(0, Math.min(1, (value - inMin) / (inMax - inMin)));
}

/** Remap pitch curve accounting for per-stem ranges. Returns 0 for unvoiced. */
export function remapPitch(value: number, stemMin = 0.01, stemMax = 0.25): number {
  if (value === 0) return 0;
  return remap(value, stemMin, stemMax);
}

/** Linear interpolation. */
export function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

/** Hex colour '#RRGGBB' to rgba string. */
export function hexToRgba(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

/** HSL colour string. */
export function hsl(h: number, s: number, l: number, a = 1): string {
  return `hsla(${h},${s}%,${l}%,${a})`;
}
