import type { StemFrame } from '../types';
import type { StemName } from '../types';
import type { CanvasLane } from './base';
import { StemRenderer } from './base';

/** Parse '#RRGGBB' to rgba string with given alpha. */
function hexToRgba(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

export class WaveRenderer extends StemRenderer {
  constructor(
    readonly stemName: StemName,
    private colour: string,
    private resolution = 200,
  ) { super(); }

  render(
    frame: StemFrame,
    _canvas: HTMLCanvasElement,
    ctx: CanvasRenderingContext2D,
    lane: CanvasLane,
    elapsed: number,
  ): void {
    const { y, height, width } = lane;
    const cy      = y + height / 2;
    const maxAmp  = height * 0.4 * frame.energy;
    const turb    = frame.flux * 0.3;

    ctx.beginPath();
    ctx.moveTo(0, cy);

    for (let i = 0; i <= this.resolution; i++) {
      const x    = (i / this.resolution) * width;
      const t    = (i / this.resolution) * Math.PI * 4 + elapsed * 0.5;
      const wave = Math.sin(t) * maxAmp;
      const noise = Math.sin(t * 7.3 + elapsed) * maxAmp * turb;
      ctx.lineTo(x, cy + wave + noise);
    }

    ctx.lineTo(width, cy);
    ctx.lineTo(0, cy);
    ctx.closePath();

    const opacity = 0.3 + frame.energy * 0.6;
    ctx.fillStyle = hexToRgba(this.colour, opacity);
    ctx.fill();

    ctx.strokeStyle = hexToRgba(this.colour, 0.8 + frame.onset * 0.2);
    ctx.lineWidth = 1 + frame.energy * 2;
    ctx.stroke();
  }
}
