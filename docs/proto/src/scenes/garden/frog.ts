import type { StemFrame } from '../../types';

/**
 * Frog's throat — driven by drums.
 * Throat sac inflates on onset, body scales with energy.
 */
export class FrogOrganism {
  opacity = 1;
  frozen = false;
  private throatDecay = 0;

  render(frame: StemFrame, ctx: CanvasRenderingContext2D, w: number, h: number): void {
    // Silence fade
    const isSilent = frame.energy < 0.05;
    this.opacity += isSilent ? -0.033 : 0.05;
    this.opacity = Math.max(0, Math.min(1, this.opacity));
    if (isSilent && this.opacity < 0.01) { this.frozen = true; return; }
    this.frozen = false;

    const groundY = h * 0.7;
    const x = w * 0.78;
    const y = groundY + h * 0.06;
    const scale = 1.0 + frame.energy * 0.3;

    if (frame.onset > 0.2) this.throatDecay = frame.onset;
    this.throatDecay *= 0.92;
    const throatScale = 1.0 + this.throatDecay * 1.5;

    ctx.save();
    ctx.globalAlpha = this.opacity;
    ctx.translate(x, y);
    ctx.scale(scale * 3, scale * 3);

    ctx.fillStyle = '#2D5A27';
    ctx.beginPath();
    ctx.ellipse(0, 0, 28, 22, 0, 0, Math.PI * 2);
    ctx.fill();

    ctx.beginPath();
    ctx.ellipse(0, -20, 18, 16, 0, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = '#1a1a1a';
    ctx.beginPath();
    ctx.arc(-8, -28, 4, 0, Math.PI * 2);
    ctx.arc(8, -28, 4, 0, Math.PI * 2);
    ctx.fill();

    const throatAlpha = 0.3 + this.throatDecay * 0.7;
    ctx.fillStyle = `rgba(123, 94, 167, ${throatAlpha})`;
    ctx.beginPath();
    ctx.ellipse(0, -6, 12 * throatScale, 10 * throatScale, 0, 0, Math.PI * 2);
    ctx.fill();

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
