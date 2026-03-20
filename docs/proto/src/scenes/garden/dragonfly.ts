import type { StemFrame } from '../../types';
import { lerp } from '../../utils';

/**
 * Dragonfly — driven by guitar.
 * Darts to random position on onset, hovers otherwise.
 * Trail on dart.
 */
export class DragonflyOrganism {
  opacity = 1;
  frozen = false;
  private x = 0;
  private y = 0;
  private targetX = 0;
  private targetY = 0;
  private trail: { x: number; y: number; alpha: number }[] = [];
  private inited = false;

  private init(w: number, h: number): void {
    this.x = w * 0.65;
    this.y = h * 0.18;
    this.targetX = this.x;
    this.targetY = this.y;
    this.inited = true;
  }

  render(frame: StemFrame, ctx: CanvasRenderingContext2D, w: number, h: number, elapsed: number): void {
    if (!this.inited) this.init(w, h);

    const isSilent = frame.energy < 0.05;
    this.opacity += isSilent ? -0.033 : 0.05;
    this.opacity = Math.max(0, Math.min(1, this.opacity));
    if (isSilent && this.opacity < 0.01) { this.frozen = true; return; }
    this.frozen = false;

    // Dart on guitar onset
    if (frame.onset > 0.3) {
      const dartDist = frame.onset * 200;
      const angle = Math.random() * Math.PI * 2;
      this.targetX = Math.max(40, Math.min(w - 40, this.x + Math.cos(angle) * dartDist));
      this.targetY = Math.max(30, Math.min(h * 0.5, this.y + Math.sin(angle) * dartDist));

      // Add trail ghost
      this.trail.push({ x: this.x, y: this.y, alpha: 0.5 });
      if (this.trail.length > 3) this.trail.shift();
    }

    // Hover vibration when not darting
    const hoverX = (Math.random() - 0.5) * 2;
    const hoverY = (Math.random() - 0.5) * 2;
    this.targetX += hoverX;
    this.targetY += hoverY;

    // Ease toward target
    this.x = lerp(this.x, this.targetX, 0.3);
    this.y = lerp(this.y, this.targetY, 0.3);

    // Draw trail
    for (const t of this.trail) {
      t.alpha *= 0.88;
      ctx.globalAlpha = t.alpha * this.opacity;
      this.drawBody(ctx, t.x, t.y, frame.energy, elapsed);
    }
    this.trail = this.trail.filter(t => t.alpha > 0.02);
    ctx.globalAlpha = this.opacity;

    // Draw dragonfly
    this.drawBody(ctx, this.x, this.y, frame.energy, elapsed);
  }

  private drawBody(ctx: CanvasRenderingContext2D, x: number, y: number, energy: number, elapsed: number): void {
    ctx.save();
    ctx.translate(x, y);
    ctx.scale(3, 3);

    // Wings — four elongated ellipses at 45° angles
    const wingBlur = energy * 6;
    ctx.shadowColor = 'rgba(0, 206, 209, 0.3)';
    ctx.shadowBlur = wingBlur;

    const wingFlutter = Math.sin(elapsed * 15) * 0.1;
    const wingPairs = [
      { angle: -Math.PI / 4 + wingFlutter, len: 22 },
      { angle: Math.PI / 4 - wingFlutter, len: 22 },
      { angle: -Math.PI / 4 - 0.3 + wingFlutter, len: 18 },
      { angle: Math.PI / 4 + 0.3 - wingFlutter, len: 18 },
    ];

    ctx.fillStyle = 'rgba(0, 206, 209, 0.25)';
    for (const wing of wingPairs) {
      ctx.beginPath();
      ctx.ellipse(
        Math.cos(wing.angle) * wing.len * 0.5,
        Math.sin(wing.angle) * wing.len * 0.5,
        wing.len,
        4,
        wing.angle,
        0,
        Math.PI * 2,
      );
      ctx.fill();
    }

    ctx.shadowBlur = 0;

    // Body — elongated
    ctx.fillStyle = '#00CED1';
    ctx.beginPath();
    ctx.ellipse(0, 0, 4, 16, 0, 0, Math.PI * 2);
    ctx.fill();

    // Head
    ctx.beginPath();
    ctx.arc(0, -16, 4, 0, Math.PI * 2);
    ctx.fill();

    // Eyes
    ctx.fillStyle = '#0A2A2A';
    ctx.beginPath();
    ctx.arc(-3, -17, 2, 0, Math.PI * 2);
    ctx.arc(3, -17, 2, 0, Math.PI * 2);
    ctx.fill();

    ctx.restore();
  }
}
