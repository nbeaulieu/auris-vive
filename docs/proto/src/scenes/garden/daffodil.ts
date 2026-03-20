import type { StemFrame } from '../../types';
import { remapPitch } from '../../utils';

/**
 * Daffodils — driven by piano.
 * 3 flowers, petal bloom from pitch, sway from energy.
 */
export class DaffodilOrganism {
  render(frame: StemFrame, ctx: CanvasRenderingContext2D, w: number, h: number, elapsed: number): void {
    const groundY = h * 0.7;
    const positions = [w * 0.3, w * 0.48, w * 0.62];

    const pitch = remapPitch(frame.pitch_curve, 0.01, 0.8);
    const petalLength = 24 + pitch * 75;
    const sway = Math.sin(elapsed * 1.5) * frame.energy * 40;

    for (let f = 0; f < 3; f++) {
      const bx = positions[f] + sway * (f === 1 ? -1 : 1);
      const stemHeight = 180 + f * 45;
      const flowerY = groundY - stemHeight;

      ctx.save();

      // Stem
      ctx.strokeStyle = '#3A7D32';
      ctx.lineWidth = 8;
      ctx.beginPath();
      ctx.moveTo(bx, groundY);
      ctx.quadraticCurveTo(bx + sway * 0.5, groundY - stemHeight * 0.5, bx + sway, flowerY);
      ctx.stroke();

      // Leaf
      ctx.fillStyle = '#3A7D32';
      ctx.beginPath();
      const leafY = groundY - stemHeight * 0.35;
      ctx.ellipse(bx + 24, leafY, 36, 12, 0.4, 0, Math.PI * 2);
      ctx.fill();

      ctx.translate(bx + sway, flowerY);

      // Petals — 6 ellipses
      const petalHue = 50 + pitch * 10;
      for (let i = 0; i < 6; i++) {
        const angle = (i / 6) * Math.PI * 2;
        ctx.save();
        ctx.rotate(angle);
        ctx.fillStyle = `hsla(${petalHue}, 90%, 55%, 0.85)`;
        ctx.beginPath();
        ctx.ellipse(0, -petalLength * 0.6, 15, petalLength, 0, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
      }

      // Centre trumpet
      ctx.fillStyle = '#FFE4A0';
      ctx.beginPath();
      ctx.arc(0, 0, 18, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = '#E8C040';
      ctx.beginPath();
      ctx.arc(0, 0, 10, 0, Math.PI * 2);
      ctx.fill();

      ctx.restore();
    }
  }
}
