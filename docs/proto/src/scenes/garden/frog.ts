import type { StemFrame } from '../../types';

/**
 * Frog's throat — driven by drums.
 * Throat sac inflates on onset, body scales with energy.
 */
export class FrogOrganism {
  private throatDecay = 0;

  render(frame: StemFrame, ctx: CanvasRenderingContext2D, w: number, h: number): void {
    const groundY = h * 0.7;
    const x = w * 0.78;
    const y = groundY + h * 0.06;
    const scale = 1.0 + frame.energy * 0.3;

    // Throat inflation with decay
    if (frame.onset > 0.2) this.throatDecay = frame.onset;
    this.throatDecay *= 0.92;
    const throatScale = 1.0 + this.throatDecay * 1.5;

    ctx.save();
    ctx.translate(x, y);
    ctx.scale(scale * 3, scale * 3);

    // Body — two overlapping circles
    ctx.fillStyle = '#2D5A27';
    ctx.beginPath();
    ctx.ellipse(0, 0, 28, 22, 0, 0, Math.PI * 2);
    ctx.fill();

    // Head
    ctx.beginPath();
    ctx.ellipse(0, -20, 18, 16, 0, 0, Math.PI * 2);
    ctx.fill();

    // Eyes
    ctx.fillStyle = '#1a1a1a';
    ctx.beginPath();
    ctx.arc(-8, -28, 4, 0, Math.PI * 2);
    ctx.arc(8, -28, 4, 0, Math.PI * 2);
    ctx.fill();

    // Throat sac
    const throatAlpha = 0.3 + this.throatDecay * 0.7;
    ctx.fillStyle = `rgba(123, 94, 167, ${throatAlpha})`;
    ctx.beginPath();
    ctx.ellipse(0, -6, 12 * throatScale, 10 * throatScale, 0, 0, Math.PI * 2);
    ctx.fill();

    // Front legs
    ctx.strokeStyle = '#2D5A27';
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(-20, 8);
    ctx.lineTo(-34, 18);
    ctx.moveTo(20, 8);
    ctx.lineTo(34, 18);
    ctx.stroke();

    ctx.restore();
  }
}
