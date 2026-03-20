import type { StemFrame } from '../../types';
import { remapPitch, lerp, hsl } from '../../utils';

/**
 * Butterfly — driven by vocals.
 * Color from pitch (violet→gold), figure-8 flight, wings fold when unvoiced.
 */
export class ButterflyOrganism {
  private phase = 0;
  private wingSpread = 0;

  render(frame: StemFrame, ctx: CanvasRenderingContext2D, w: number, h: number, elapsed: number): void {
    const voiced = frame.pitch_curve > 0;

    // Figure-8 flight path (Lissajous)
    const speed = 0.3 + frame.energy * 0.7;
    this.phase += speed * 0.016;
    const cx = w * 0.45 + Math.sin(this.phase) * w * 0.12;
    const cy = h * 0.28 + Math.sin(this.phase * 2) * h * 0.06;

    // Wing spread: open when voiced, fold when not
    const targetSpread = voiced ? 0.6 + frame.energy * 0.4 : 0.1;
    this.wingSpread = lerp(this.wingSpread, targetSpread, 0.08);

    // Color from pitch — violet (260°) → gold (360°/0°)
    const pitchVal = remapPitch(frame.pitch_curve, 0.01, 0.93);
    const hue = voiced ? 260 + pitchVal * 100 : 260;
    const sat = 60 + pitchVal * 30;
    const lit = 40 + frame.energy * 20;

    // Breathing iridescence
    const breathAlpha = 0.7 + Math.sin(elapsed * 0.3 * Math.PI * 2) * 0.15;

    const wingAngle = this.wingSpread * Math.PI * 0.45;

    ctx.save();
    ctx.translate(cx, cy);
    ctx.scale(3, 3);

    // Wing flutter
    const flutter = Math.sin(elapsed * (3 + frame.energy * 8)) * 0.15;
    const leftAngle = wingAngle + flutter;
    const rightAngle = wingAngle - flutter;

    // Draw wings — mirrored bezier shapes
    this.drawWing(ctx, -1, leftAngle, hue, sat, lit, breathAlpha);
    this.drawWing(ctx, 1, rightAngle, hue, sat, lit, breathAlpha);

    // Body
    ctx.fillStyle = '#1A1428';
    ctx.beginPath();
    ctx.ellipse(0, 0, 3, 14, 0, 0, Math.PI * 2);
    ctx.fill();

    // Antennae
    ctx.strokeStyle = '#1A1428';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(-1, -12);
    ctx.quadraticCurveTo(-8, -24, -12, -22);
    ctx.moveTo(1, -12);
    ctx.quadraticCurveTo(8, -24, 12, -22);
    ctx.stroke();

    ctx.restore();
  }

  private drawWing(
    ctx: CanvasRenderingContext2D,
    side: number,
    angle: number,
    hue: number,
    sat: number,
    lit: number,
    alpha: number,
  ): void {
    ctx.save();
    ctx.scale(side, 1);

    // Upper wing
    ctx.fillStyle = hsl(hue, sat, lit, alpha);
    ctx.beginPath();
    ctx.moveTo(0, -4);
    ctx.bezierCurveTo(
      Math.cos(angle) * 30, -20,
      Math.cos(angle) * 40, -10,
      Math.cos(angle) * 28, 2,
    );
    ctx.closePath();
    ctx.fill();

    // Lower wing — smaller, pointed
    ctx.fillStyle = hsl(hue + 15, sat - 5, lit + 5, alpha * 0.85);
    ctx.beginPath();
    ctx.moveTo(0, 2);
    ctx.bezierCurveTo(
      Math.cos(angle) * 22, 4,
      Math.cos(angle) * 28, 14,
      Math.cos(angle) * 14, 16,
    );
    ctx.closePath();
    ctx.fill();

    ctx.restore();
  }
}
