import type { StemName, StemFrame } from '../types';

export abstract class Scene {
  abstract mount(canvas: HTMLCanvasElement): void;
  abstract unmount(): void;
  abstract render(
    frames: Record<StemName, StemFrame>,
    ctx: CanvasRenderingContext2D,
    width: number,
    height: number,
    elapsed: number,
  ): void;
}
