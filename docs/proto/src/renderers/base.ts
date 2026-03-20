import type { StemName, StemFrame } from '../types';

export interface CanvasLane {
  y:      number;
  height: number;
  width:  number;
}

export abstract class StemRenderer {
  abstract readonly stemName: StemName;

  abstract render(
    frame:   StemFrame,
    canvas:  HTMLCanvasElement,
    ctx:     CanvasRenderingContext2D,
    lane:    CanvasLane,
    elapsed: number,
  ): void;
}
