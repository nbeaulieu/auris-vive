import type { CurvesData, StemName, StemFrame } from './types';

export class CurvePlayer {
  constructor(private data: CurvesData) {}

  frameAt(timeSeconds: number): Record<StemName, StemFrame> {
    const frame = Math.min(
      Math.max(Math.floor(timeSeconds * this.data.frame_rate), 0),
      this.data.n_frames - 1,
    );

    const result = {} as Record<StemName, StemFrame>;
    for (const [stemName, curves] of Object.entries(this.data.stems)) {
      result[stemName as StemName] = {
        energy:     curves.energy[frame]     ?? 0,
        brightness: curves.brightness[frame] ?? 0,
        onset:      curves.onset[frame]      ?? 0,
        warmth:     curves.warmth[frame]     ?? 0,
        texture:    curves.texture[frame]    ?? 0,
        flux:       curves.flux[frame]       ?? 0,
      };
    }
    return result;
  }
}
