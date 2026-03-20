import type { StemFrame } from '../../types';
import { remapPitch, hsl } from '../../utils';

interface Mushroom {
  x: number;       // x offset from cluster centre (px)
  y: number;       // y offset from ground (px, negative = taller)
  stemW: number;   // stem width
  stemH: number;   // stem height
  capW: number;    // cap half-width
  capH: number;    // cap height
  phase: number;   // sway phase
  spots: { dx: number; dy: number; rx: number; ry: number }[];
}

/**
 * Psychedelic mushrooms — driven by bass.
 * Cap pulse from energy, color shift from pitch (violet→teal).
 */
export class MushroomsOrganism {
  opacity = 1;
  frozen = false;
  private mushrooms: Mushroom[] = [];
  private inited = false;

  private init(w: number, h: number): void {
    const cx = w * 0.32;
    const groundY = h * 0.7;

    // 5 mushrooms — tallest at back, shortest at front
    const defs = [
      { x: -60, y: 0,    stemW: 18, stemH: 140, capW: 55, capH: 40, phase: 0 },
      { x: 20,  y: -10,  stemW: 22, stemH: 180, capW: 70, capH: 50, phase: 1.3 },
      { x: -20, y: -5,   stemW: 16, stemH: 110, capW: 45, capH: 35, phase: 2.7 },
      { x: 70,  y: 5,    stemW: 20, stemH: 160, capW: 60, capH: 45, phase: 0.8 },
      { x: 110, y: 8,    stemW: 14, stemH: 90,  capW: 40, capH: 30, phase: 3.5 },
    ];

    this.mushrooms = defs.map(d => ({
      ...d,
      x: cx + d.x,
      y: groundY + d.y,
      spots: Array.from({ length: 3 + Math.floor(Math.random() * 3) }, () => ({
        dx: (Math.random() - 0.5) * d.capW * 1.2,
        dy: -d.capH * 0.3 - Math.random() * d.capH * 0.5,
        rx: 4 + Math.random() * 6,
        ry: 3 + Math.random() * 4,
      })),
    }));
    this.inited = true;
  }

  render(frame: StemFrame, ctx: CanvasRenderingContext2D, w: number, h: number, elapsed: number): void {
    if (!this.inited) this.init(w, h);

    // Silence fade
    const isSilent = frame.energy < 0.05;
    this.opacity += isSilent ? -0.033 : 0.05;
    this.opacity = Math.max(0, Math.min(1, this.opacity));
    if (isSilent && this.opacity < 0.01) { this.frozen = true; return; }
    this.frozen = false;

    // Color from bass pitch
    const pitchNorm = remapPitch(frame.pitch_curve, 0.01, 0.07);
    const hue = 260 + pitchNorm * 120;
    const capColor = hsl(hue, 80, 30 + frame.energy * 40);
    const glowColor = hsl(hue, 100, 60);

    // Cap pulse
    const pulse = 1 + frame.energy * 0.4;
    const glowBlur = frame.energy * 60;

    ctx.save();
    ctx.globalAlpha = this.opacity;

    // Draw back-to-front (tallest first)
    const sorted = [...this.mushrooms].sort((a, b) => a.stemH - b.stemH).reverse();

    for (const m of sorted) {
      const sway = Math.sin(elapsed * 0.8 + m.phase) * 3 * frame.energy;
      const baseX = m.x + sway;
      const baseY = m.y;
      const capY = baseY - m.stemH;

      ctx.save();

      // Stem
      const stemLeft = baseX - m.stemW / 2;
      ctx.fillStyle = '#E8E0D5';
      ctx.beginPath();
      this.roundedRect(ctx, stemLeft + sway * 0.3, capY + m.capH * 0.6, m.stemW, m.stemH - m.capH * 0.4, m.stemW / 3);
      ctx.fill();

      // Bioluminescent ring under cap
      ctx.shadowColor = glowColor;
      ctx.shadowBlur = glowBlur;
      ctx.fillStyle = `hsla(${hue}, 100%, 60%, ${0.15 + frame.energy * 0.3})`;
      ctx.beginPath();
      ctx.ellipse(baseX + sway, capY + m.capH * 0.7, m.capW * pulse * 0.8, 6, 0, 0, Math.PI * 2);
      ctx.fill();

      // Cap — dome shape via arc
      ctx.shadowBlur = glowBlur * 0.5;
      ctx.fillStyle = capColor;
      ctx.beginPath();
      ctx.ellipse(baseX + sway, capY, m.capW * pulse, m.capH * pulse, 0, Math.PI, 0);
      // Flat bottom
      ctx.closePath();
      ctx.fill();

      ctx.shadowBlur = 0;

      // Spots
      ctx.fillStyle = 'rgba(232, 224, 213, 0.6)';
      for (const spot of m.spots) {
        ctx.beginPath();
        ctx.ellipse(
          baseX + sway + spot.dx * pulse * 0.8,
          capY + spot.dy * pulse,
          spot.rx * pulse,
          spot.ry * pulse,
          0, 0, Math.PI * 2,
        );
        ctx.fill();
      }

      ctx.restore();
    }

    ctx.restore();
  }

  private roundedRect(
    ctx: CanvasRenderingContext2D,
    x: number, y: number, w: number, h: number, r: number,
  ): void {
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + r);
    ctx.lineTo(x + w, y + h - r);
    ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    ctx.lineTo(x + r, y + h);
    ctx.quadraticCurveTo(x, y + h, x, y + h - r);
    ctx.lineTo(x, y + r);
    ctx.quadraticCurveTo(x, y, x + r, y);
  }
}
