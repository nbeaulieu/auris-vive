import type { StemFrame } from '../../types';
import { hexToRgba } from '../../utils';

/**
 * Snail — driven by bass.
 * Crawls left→right, speed from energy. Spiral shell.
 */
export class SnailOrganism {
  private x = 0;
  private trail: { x: number; y: number; age: number }[] = [];

  render(frame: StemFrame, ctx: CanvasRenderingContext2D, w: number, h: number): void {
    const groundY = h * 0.7;
    const y = groundY + h * 0.08;

    // Movement — speed from bass energy
    this.x += frame.energy * 1.2;
    if (this.x > w + 60) this.x = -60;

    // Trail
    this.trail.push({ x: this.x, y, age: 0 });
    this.trail = this.trail.filter(t => {
      t.age += 1 / 60;
      return t.age < 2;
    });

    // Draw trail
    for (const t of this.trail) {
      const alpha = (1 - t.age / 2) * 0.08;
      ctx.fillStyle = hexToRgba('#A084C8', alpha);
      ctx.beginPath();
      ctx.ellipse(t.x, t.y + 8, 3, 1.5, 0, 0, Math.PI * 2);
      ctx.fill();
    }

    ctx.save();
    ctx.translate(this.x, y);
    ctx.scale(3, 3);

    // Body
    const stretch = 1 + frame.energy * 0.15;
    ctx.fillStyle = '#C9A96E';
    ctx.beginPath();
    ctx.ellipse(0, 6, 24 * stretch, 8, 0, 0, Math.PI * 2);
    ctx.fill();

    // Shell — spiral via concentric arcs
    const shellX = -4;
    const shellY = -6;
    const shellR = 16;
    const glow = frame.energy * 8;

    ctx.shadowColor = '#A084C8';
    ctx.shadowBlur = glow;

    ctx.fillStyle = '#8B6914';
    ctx.beginPath();
    ctx.arc(shellX, shellY, shellR, 0, Math.PI * 2);
    ctx.fill();

    // Spiral lines
    ctx.strokeStyle = '#6B4F0A';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    for (let a = 0; a < Math.PI * 4; a += 0.1) {
      const r = (a / (Math.PI * 4)) * shellR * 0.8;
      const sx = shellX + Math.cos(a) * r;
      const sy = shellY + Math.sin(a) * r;
      if (a === 0) ctx.moveTo(sx, sy);
      else ctx.lineTo(sx, sy);
    }
    ctx.stroke();

    ctx.shadowBlur = 0;

    // Eye stalks
    ctx.strokeStyle = '#C9A96E';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(20, 0);
    ctx.lineTo(26, -12);
    ctx.moveTo(16, 0);
    ctx.lineTo(20, -14);
    ctx.stroke();

    ctx.fillStyle = '#1a1a1a';
    ctx.beginPath();
    ctx.arc(26, -12, 2, 0, Math.PI * 2);
    ctx.arc(20, -14, 2, 0, Math.PI * 2);
    ctx.fill();

    ctx.restore();
  }
}
