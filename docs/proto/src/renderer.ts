import type { StemName, StemFrame } from './types';
import type { CanvasLane } from './renderers/base';
import type { StemRenderer } from './renderers/base';
import { BACKGROUND } from './palette';

const STEM_ORDER: StemName[] = ['drums', 'bass', 'vocals', 'other', 'piano', 'guitar'];

export class CanvasRenderer {
  private renderers: Map<StemName, StemRenderer>;

  constructor(
    private canvas: HTMLCanvasElement,
    renderers: StemRenderer[],
  ) {
    this.renderers = new Map(renderers.map(r => [r.stemName, r]));
  }

  render(frames: Record<StemName, StemFrame>, elapsed: number): void {
    const ctx = this.canvas.getContext('2d')!;
    const laneHeight = this.canvas.height / STEM_ORDER.length;

    ctx.fillStyle = BACKGROUND;
    ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

    STEM_ORDER.forEach((stemName, i) => {
      const renderer = this.renderers.get(stemName);
      const frame    = frames[stemName];
      if (!renderer || !frame) return;

      const lane: CanvasLane = {
        y:      i * laneHeight,
        height: laneHeight,
        width:  this.canvas.width,
      };
      renderer.render(frame, this.canvas, ctx, lane, elapsed);
    });
  }
}
