import type { StemFrame } from '../../types';

interface Bee {
  angle: number;
  r: number;
  x: number;
  y: number;
  speed: number;
}

/**
 * Bees — driven by other stem.
 * Swarm orbits a drifting centre. Scatter on onset.
 */
export class BeesOrganism {
  opacity = 1;
  frozen = false;
  private bees: Bee[] = [];
  private swarmCx = 0;
  private swarmCy = 0;
  private swarmPhase = 0;
  private inited = false;

  private init(w: number, h: number): void {
    this.swarmCx = w * 0.25;
    this.swarmCy = h * 0.22;
    this.bees = Array.from({ length: 12 }, (_, i) => ({
      angle: (i / 12) * Math.PI * 2,
      r: 20 + Math.random() * 20,
      x: 0,
      y: 0,
      speed: 0.03 + Math.random() * 0.04,
    }));
    this.inited = true;
  }

  render(frame: StemFrame, ctx: CanvasRenderingContext2D, w: number, h: number, _elapsed: number): void {
    if (!this.inited) this.init(w, h);

    const isSilent = frame.energy < 0.05;
    this.opacity += isSilent ? -0.033 : 0.05;
    this.opacity = Math.max(0, Math.min(1, this.opacity));
    if (isSilent && this.opacity < 0.01) { this.frozen = true; return; }
    this.frozen = false;

    // Swarm centre drifts slowly
    this.swarmPhase += 0.005;
    const baseCx = w * 0.25 + Math.sin(this.swarmPhase) * w * 0.08;
    const baseCy = h * 0.22 + Math.cos(this.swarmPhase * 0.7) * h * 0.04;
    this.swarmCx += (baseCx - this.swarmCx) * 0.02;
    this.swarmCy += (baseCy - this.swarmCy) * 0.02;

    ctx.save();
    ctx.globalAlpha = this.opacity;

    // Active bee count scales with energy
    const activeCount = Math.round(8 + frame.energy * 4);

    for (let i = 0; i < this.bees.length; i++) {
      const bee = this.bees[i];
      if (i >= activeCount) continue;

      bee.angle += bee.speed + frame.energy * 0.1;
      bee.r = 60 + frame.energy * 120 + frame.onset * 180;
      bee.x = this.swarmCx + Math.cos(bee.angle) * bee.r;
      bee.y = this.swarmCy + Math.sin(bee.angle * 0.8) * bee.r * 0.6;

      // Clamp to canvas
      bee.x = Math.max(10, Math.min(w - 10, bee.x));
      bee.y = Math.max(10, Math.min(h * 0.6, bee.y));

      const energyDarken = 1 - frame.energy * 0.3;

      ctx.save();
      ctx.translate(bee.x, bee.y);
      ctx.scale(3, 3);

      // Body
      ctx.fillStyle = `rgba(${Math.round(201 * energyDarken)},${Math.round(169 * energyDarken)},${Math.round(110 * energyDarken)},0.9)`;
      ctx.beginPath();
      ctx.ellipse(0, 0, 5, 3.5, 0, 0, Math.PI * 2);
      ctx.fill();

      // Stripes
      ctx.fillStyle = 'rgba(30,20,10,0.5)';
      ctx.fillRect(-2, -3, 1.5, 6);
      ctx.fillRect(1, -3, 1.5, 6);

      // Wings — blur with energy
      const wingBlur = frame.energy * 4;
      ctx.shadowColor = 'rgba(255,255,255,0.3)';
      ctx.shadowBlur = wingBlur;
      ctx.fillStyle = 'rgba(255,255,255,0.25)';
      ctx.beginPath();
      ctx.ellipse(-2, -4, 4, 2.5, -0.4, 0, Math.PI * 2);
      ctx.fill();
      ctx.beginPath();
      ctx.ellipse(2, -4, 4, 2.5, 0.4, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;

      ctx.restore();
    }

    ctx.restore();
  }
}
