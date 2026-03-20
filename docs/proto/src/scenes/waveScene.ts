import type { StemName, StemFrame } from '../types';
import { Scene } from './base';
import { STEM_COLOURS, BACKGROUND } from '../palette';
import { hexToRgba } from '../utils';

const STEM_ORDER: StemName[] = ['drums', 'bass', 'vocals', 'other', 'piano', 'guitar'];
const RESOLUTION = 200;

export class WaveScene extends Scene {
  mount(_canvas: HTMLCanvasElement): void {}
  unmount(): void {}

  render(
    frames: Record<StemName, StemFrame>,
    ctx: CanvasRenderingContext2D,
    width: number,
    height: number,
    elapsed: number,
    stemEnabled: Record<StemName, boolean>,
  ): void {
    ctx.fillStyle = BACKGROUND;
    ctx.fillRect(0, 0, width, height);

    const laneHeight = height / STEM_ORDER.length;

    STEM_ORDER.forEach((stemName, i) => {
      if (!stemEnabled[stemName]) return;
      const frame = frames[stemName];
      if (!frame) return;

      const y      = i * laneHeight;
      const cy     = y + laneHeight / 2;
      const maxAmp = laneHeight * 0.4 * frame.energy;
      const turb   = frame.flux * 0.3;
      const colour = STEM_COLOURS[stemName];

      ctx.beginPath();
      ctx.moveTo(0, cy);

      for (let j = 0; j <= RESOLUTION; j++) {
        const x    = (j / RESOLUTION) * width;
        const t    = (j / RESOLUTION) * Math.PI * 4 + elapsed * 0.5;
        const wave = Math.sin(t) * maxAmp;
        const noise = Math.sin(t * 7.3 + elapsed) * maxAmp * turb;
        ctx.lineTo(x, cy + wave + noise);
      }

      ctx.lineTo(width, cy);
      ctx.lineTo(0, cy);
      ctx.closePath();

      const opacity = 0.3 + frame.energy * 0.6;
      ctx.fillStyle = hexToRgba(colour, opacity);
      ctx.fill();

      ctx.strokeStyle = hexToRgba(colour, 0.8 + frame.onset * 0.2);
      ctx.lineWidth = 1 + frame.energy * 2;
      ctx.stroke();
    });
  }
}
