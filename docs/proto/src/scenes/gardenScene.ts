import type { StemName, StemFrame } from '../types';
import { Scene } from './base';
import { hexToRgba } from '../utils';
import { FrogOrganism } from './garden/frog';
import { MushroomsOrganism } from './garden/mushrooms';
import { ButterflyOrganism } from './garden/butterfly';
import { BeesOrganism } from './garden/bees';
import { DaffodilOrganism } from './garden/daffodil';
import { DragonflyOrganism } from './garden/dragonfly';

const GROUND_LINE_COLOR = 'rgba(164, 132, 200, 0.08)';

interface Firefly { x: number; y: number; }

export class GardenScene extends Scene {
  private frog = new FrogOrganism();
  private mushrooms = new MushroomsOrganism();
  private butterfly = new ButterflyOrganism();
  private bees = new BeesOrganism();
  private daffodil = new DaffodilOrganism();
  private dragonfly = new DragonflyOrganism();

  private fireflies: Firefly[] = [];
  private inited = false;

  mount(_canvas: HTMLCanvasElement): void {}
  unmount(): void {}

  private init(w: number, h: number): void {
    this.fireflies = Array.from({ length: 5 }, () => ({
      x: Math.random() * w,
      y: Math.random() * h * 0.65,
    }));
    this.inited = true;
  }

  render(
    frames: Record<StemName, StemFrame>,
    ctx: CanvasRenderingContext2D,
    width: number,
    height: number,
    elapsed: number,
    stemEnabled: Record<StemName, boolean>,
  ): void {
    if (!this.inited) this.init(width, height);

    const groundY = height * 0.7;

    // ── Sky gradient ────────────────────────────────────────────────────
    const skyGrad = ctx.createLinearGradient(0, 0, 0, groundY);
    skyGrad.addColorStop(0, '#06060A');
    skyGrad.addColorStop(1, '#1A1428');
    ctx.fillStyle = skyGrad;
    ctx.fillRect(0, 0, width, groundY);

    // ── Ground gradient ─────────────────────────────────────────────────
    const groundGrad = ctx.createLinearGradient(0, groundY, 0, height);
    groundGrad.addColorStop(0, '#1A1428');
    groundGrad.addColorStop(1, '#0E0B18');
    ctx.fillStyle = groundGrad;
    ctx.fillRect(0, groundY, width, height - groundY);

    // ── Atmospheric foliage blobs ───────────────────────────────────────
    ctx.save();
    ctx.fillStyle = 'rgba(123, 94, 167, 0.04)';
    ctx.shadowColor = 'rgba(123, 94, 167, 0.04)';
    ctx.shadowBlur = 80;
    const blobPositions = [
      { x: width * 0.15, y: groundY - 40, rx: 300, ry: 120 },
      { x: width * 0.52, y: groundY - 20, rx: 400, ry: 140 },
      { x: width * 0.85, y: groundY - 30, rx: 250, ry: 100 },
    ];
    for (const b of blobPositions) {
      ctx.beginPath();
      ctx.ellipse(b.x, b.y, b.rx, b.ry, 0, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.shadowBlur = 0;
    ctx.restore();

    // ── Ground line ─────────────────────────────────────────────────────
    ctx.strokeStyle = GROUND_LINE_COLOR;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, groundY);
    ctx.lineTo(width, groundY);
    ctx.stroke();

    // ── Fireflies (music-independent) ───────────────────────────────────
    this.fireflies.forEach((f, i) => {
      f.x += Math.sin(elapsed * 0.3 + i) * 0.4;
      f.y += Math.cos(elapsed * 0.2 + i * 1.3) * 0.3;
      const opacity = 0.3 + 0.6 * (0.5 + 0.5 * Math.sin(elapsed * 0.7 + i * 2));
      ctx.beginPath();
      ctx.arc(f.x, f.y, 2, 0, Math.PI * 2);
      ctx.fillStyle = hexToRgba('#C9A96E', opacity);
      ctx.fill();
    });

    // ── Organisms (back to front, respecting stemEnabled) ───────────────
    if (stemEnabled.bass)   this.mushrooms.render(frames.bass, ctx, width, height, elapsed);
    if (stemEnabled.piano)  this.daffodil.render(frames.piano, ctx, width, height, elapsed);
    if (stemEnabled.drums)  this.frog.render(frames.drums, ctx, width, height);
    if (stemEnabled.other)  this.bees.render(frames.other, ctx, width, height, elapsed);
    if (stemEnabled.guitar) this.dragonfly.render(frames.guitar, ctx, width, height, elapsed);
    if (stemEnabled.vocals) this.butterfly.render(frames.vocals, ctx, width, height, elapsed);
  }
}
