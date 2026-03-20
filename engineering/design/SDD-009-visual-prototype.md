# SDD-009 — Visual prototype (web)

| Field      | Value                                                          |
|------------|----------------------------------------------------------------|
| Status     | Draft                                                          |
| Date       | 2026-03-19                                                     |
| Relates to | SDD-008 (analyse), ADR-006 (client integration)               |
| Covers     | Static web prototype — audio playback + per-stem wave visuals  |

---

## Table of contents

1. [Purpose and scope](#1-purpose-and-scope)
2. [Architecture](#2-architecture)
3. [Build pipeline: curves → JSON bundle](#3-build-pipeline)
4. [TypeScript app structure](#4-typescript-app-structure)
5. [Audio engine](#5-audio-engine)
6. [Curve player](#6-curve-player)
7. [Renderer architecture](#7-renderer-architecture)
8. [WaveRenderer v1](#8-waverenderer-v1)
9. [Brand palette and visual language](#9-brand-palette)
10. [GitHub Pages deployment](#10-github-pages-deployment)
11. [Open questions](#11-open-questions)

---

## 1. Purpose and scope

A self-contained static web prototype that:

- Plays a 30-second audio clip in the browser
- Renders six simultaneous wave visualisations on one canvas — one per stem
- Drives each wave from the pre-computed `StemCurves` data
- Deploys to GitHub Pages with `git push`

**Design intent:** one canvas, six waves playing together. Each stem has
its own visual identity. The wave is v1 — the renderer per stem is
swappable. Drums could become butterflies. Bass could become a tide.
The architecture supports this without touching the other stems.

**What this is not:**
- A real-time pipeline (curves are pre-computed and shipped as JSON)
- A production client (no auth, no API, no job queue)
- A final visual design (v1 placeholder waves only)

---

## 2. Architecture

```
Python (one-time export)
  scripts/export-curves.py
    reads:  test_audio/<slug>/curves/*.npy
            test_audio/<slug>/clip.wav
    writes: docs/proto/data/<slug>/curves.json
            docs/proto/data/<slug>/audio.wav

Browser (static, no server)
  docs/proto/
    index.html
    src/
      main.ts          — entry point, song selector
      audio.ts         — AudioContext wrapper + playhead
      curvePlayer.ts   — indexes into curves at current playhead
      renderer.ts      — canvas orchestrator, calls stem renderers
      renderers/
        base.ts        — StemRenderer abstract class
        wave.ts        — WaveRenderer (v1 all stems)
      palette.ts       — Auris Vive brand colours
      types.ts         — StemCurves, StemName, Frame types
    data/
      <slug>/
        curves.json    — all 6 stems × 6 curves × T frames
        audio.wav      — 30s clip

Deployment: GitHub Pages from docs/ directory
```

---

## 3. Build pipeline

### `scripts/export-curves.py`

Reads `.npy` curve files and `clip.wav` from `test_audio/`, writes a
self-contained JSON bundle to `docs/proto/data/`.

```python
# Output format: curves.json
{
  "slug":       "piano-man",
  "duration_s": 30.04,
  "frame_rate": 100.0,
  "n_frames":   3004,
  "stems": {
    "drums": {
      "energy":     [0.12, 0.45, 0.67, ...],   # T floats, 2dp precision
      "brightness": [0.33, 0.41, 0.39, ...],
      "onset":      [0.01, 0.88, 0.02, ...],
      "warmth":     [0.55, 0.60, 0.58, ...],
      "texture":    [0.22, 0.19, 0.25, ...],
      "flux":       [0.08, 0.91, 0.03, ...]
    },
    "bass":   { ... },
    "vocals": { ... },
    "other":  { ... },
    "piano":  { ... },
    "guitar": { ... }
  }
}
```

Float values rounded to 2 decimal places to keep JSON size reasonable.
A 30s clip at 100fps = 3000 frames × 6 stems × 6 curves × ~5 bytes = ~540KB.
Gzip compression (served by GitHub Pages) reduces this to ~80KB.

Audio is copied as-is to `docs/proto/data/<slug>/audio.wav`.

---

## 4. TypeScript app structure

### `types.ts`

```typescript
export type StemName = 'drums' | 'bass' | 'vocals' | 'other' | 'piano' | 'guitar';

export interface StemFrame {
  energy:     number;   // loudness         [0, 1]
  brightness: number;   // spectral centroid [0, 1]
  onset:      number;   // transient strength [0, 1]
  warmth:     number;   // low-band energy   [0, 1]
  texture:    number;   // flatness          [0, 1]
  flux:       number;   // rate of change    [0, 1]
}

export interface CurvesData {
  slug:       string;
  duration_s: number;
  frame_rate: number;
  n_frames:   number;
  stems:      Record<StemName, Record<keyof StemFrame, number[]>>;
}
```

### `palette.ts`

```typescript
// Auris Vive brand palette — one colour per stem
export const STEM_COLOURS: Record<StemName, string> = {
  drums:  '#7B5EA7',   // Violet
  bass:   '#A084C8',   // Iris
  vocals: '#C9A96E',   // Gold
  other:  '#E8E0D5',   // Pearl
  piano:  '#A084C8',   // Iris (variant)
  guitar: '#7B5EA7',   // Violet (variant)
};

export const BACKGROUND = '#06060A';  // Void
```

---

## 5. Audio engine

### `audio.ts`

```typescript
export class AudioEngine {
  private ctx:    AudioContext;
  private source: AudioBufferSourceNode | null = null;
  private buffer: AudioBuffer | null = null;
  private startedAt = 0;
  private offset    = 0;
  private _playing  = false;

  async load(url: string): Promise<void> {
    this.ctx = new AudioContext();
    const response = await fetch(url);
    const arrayBuffer = await response.arrayBuffer();
    this.buffer = await this.ctx.decodeAudioData(arrayBuffer);
  }

  play(): void {
    if (!this.buffer || this._playing) return;
    this.source = this.ctx.createBufferSource();
    this.source.buffer = this.buffer;
    this.source.connect(this.ctx.destination);
    this.source.start(0, this.offset);
    this.startedAt = this.ctx.currentTime - this.offset;
    this._playing = true;
    this.source.onended = () => { this._playing = false; };
  }

  pause(): void {
    if (!this._playing) return;
    this.offset = this.currentTime;
    this.source?.stop();
    this._playing = false;
  }

  get currentTime(): number {
    if (this._playing) return this.ctx.currentTime - this.startedAt;
    return this.offset;
  }

  get playing(): boolean { return this._playing; }
}
```

---

## 6. Curve player

### `curvePlayer.ts`

```typescript
export class CurvePlayer {
  constructor(private data: CurvesData) {}

  frameAt(timeSeconds: number): Record<StemName, StemFrame> {
    const frame = Math.min(
      Math.floor(timeSeconds * this.data.frame_rate),
      this.data.n_frames - 1,
    );

    const result = {} as Record<StemName, StemFrame>;
    for (const [stemName, curves] of Object.entries(this.data.stems)) {
      result[stemName as StemName] = {
        energy:     curves.energy[frame]     ?? 0,
        brightness: curves.brightness[frame] ?? 0,
        onset:      curves.onset[frame]      ?? 0,
        warmth:     curves.warmth[frame]     ?? 0,
        texture:    curves.texture[frame]    ?? 0,
        flux:       curves.flux[frame]       ?? 0,
      };
    }
    return result;
  }
}
```

---

## 7. Renderer architecture

### `renderers/base.ts`

```typescript
export abstract class StemRenderer {
  abstract readonly stemName: StemName;

  abstract render(
    frame:   StemFrame,
    canvas:  HTMLCanvasElement,
    ctx:     CanvasRenderingContext2D,
    lane:    CanvasLane,        // y position and height allocated to this stem
    elapsed: number,            // seconds since playback started (for animation)
  ): void;
}

export interface CanvasLane {
  y:      number;   // top of this stem's lane in canvas pixels
  height: number;   // height of this stem's lane
  width:  number;   // canvas width
}
```

The canvas is divided into 6 equal horizontal lanes — one per stem. Each
renderer draws only within its lane. The orchestrator allocates lanes and
calls each renderer in order.

### `renderer.ts` — Canvas orchestrator

```typescript
export class CanvasRenderer {
  private renderers: Map<StemName, StemRenderer>;

  constructor(
    private canvas: HTMLCanvasElement,
    renderers: StemRenderer[],
  ) {
    this.renderers = new Map(renderers.map(r => [r.stemName, r]));
  }

  render(frames: Record<StemName, StemFrame>, elapsed: number): void {
    const ctx = this.canvas.getContext('2d')!;
    const laneHeight = this.canvas.height / STEM_ORDER.length;

    ctx.fillStyle = BACKGROUND;
    ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

    STEM_ORDER.forEach((stemName, i) => {
      const renderer = this.renderers.get(stemName);
      const frame    = frames[stemName];
      if (!renderer || !frame) return;

      const lane: CanvasLane = {
        y:      i * laneHeight,
        height: laneHeight,
        width:  this.canvas.width,
      };
      renderer.render(frame, this.canvas, ctx, lane, elapsed);
    });
  }
}

const STEM_ORDER: StemName[] = ['drums', 'bass', 'vocals', 'other', 'piano', 'guitar'];
```

---

## 8. WaveRenderer v1

Each stem renders as a horizontal wave in its lane. The wave is driven by:

- **amplitude** → wave height (how tall the peaks are)
- **energy** → wave brightness / opacity
- **flux** → wave turbulence (adds high-frequency noise to the wave path)
- **brightness** → subtle hue shift along the wave

The wave is drawn as a filled path from left to right across the lane,
centred vertically in the lane.

```typescript
export class WaveRenderer extends StemRenderer {
  constructor(
    readonly stemName: StemName,
    private colour: string,
    private resolution = 200,  // number of points along the wave
  ) { super(); }

  render(frame: StemFrame, canvas: HTMLCanvasElement,
         ctx: CanvasRenderingContext2D, lane: CanvasLane, elapsed: number): void {

    const { y, height, width } = lane;
    const cy      = y + height / 2;
    const maxAmp  = height * 0.4 * frame.energy;
    const turb    = frame.flux * 0.3;

    ctx.beginPath();
    ctx.moveTo(0, cy);

    for (let i = 0; i <= this.resolution; i++) {
      const x    = (i / this.resolution) * width;
      const t    = (i / this.resolution) * Math.PI * 4 + elapsed * 0.5;
      const wave = Math.sin(t) * maxAmp;
      const noise = Math.sin(t * 7.3 + elapsed) * maxAmp * turb;
      ctx.lineTo(x, cy + wave + noise);
    }

    ctx.lineTo(width, cy);
    ctx.lineTo(0, cy);
    ctx.closePath();

    // Fill with brand colour, opacity driven by energy
    const opacity = 0.3 + frame.energy * 0.6;
    ctx.fillStyle = hexToRgba(this.colour, opacity);
    ctx.fill();

    // Bright stroke on top
    ctx.strokeStyle = hexToRgba(this.colour, 0.8 + frame.onset * 0.2);
    ctx.lineWidth = 1 + frame.energy * 2;
    ctx.stroke();
  }
}
```

---

## 9. Brand palette and visual language

All colours from `palette.ts` above. Background is always Void `#06060A`.

Stem colour assignments (v1):

| Stem   | Colour  | Hex       | Rationale |
|--------|---------|-----------|-----------|
| drums  | Violet  | `#7B5EA7` | Primary accent — most visually dominant |
| bass   | Iris    | `#A084C8` | Secondary accent — complementary to violet |
| vocals | Gold    | `#C9A96E` | Brand mark colour — most precious element |
| other  | Pearl   | `#E8E0D5` | Neutral — catch-all stem |
| piano  | Iris    | `#A084C8` | Same family as bass |
| guitar | Violet  | `#7B5EA7` | Same family as drums |

Wave opacity and size are driven entirely by the curves — the visual stays
calm when the music is quiet and alive when it peaks.

---

## 10. GitHub Pages deployment

### Setup (one-time)

In GitHub repo settings → Pages → Source: `Deploy from branch` →
Branch: `main` → Folder: `/docs`.

### Structure

```
docs/
  proto/
    index.html
    dist/           ← Vite build output
    data/
      tswift/
        curves.json
        audio.wav
      piano-man/
        curves.json
        audio.wav
      ...
```

### `package.json` (in `docs/proto/`)

```json
{
  "name": "auris-vive-proto",
  "scripts": {
    "dev":   "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "devDependencies": {
    "typescript": "^5.0",
    "vite": "^5.0"
  },
  "dependencies": {
    "three": "^0.163"
  }
}
```

### Deployment workflow

```bash
# 1. Export curves for all processed songs
python3 scripts/export-curves.py

# 2. Build the TypeScript app
cd docs/proto && npm run build

# 3. Push — GitHub Pages auto-deploys
git add docs/
git commit -m "proto: update visual prototype"
git push
```

---

## 11. Open questions

| ID | Question | Owner | Target |
|----|----------|-------|--------|
| Q-VIS-1 | Stem lane layout — equal horizontal bands is v1. Should lanes be weighted by stem energy? | Design | Post-prototype |
| Q-VIS-2 | Should stems be visually labelled (drum/bass/etc) or anonymous in the final product? | Design/Product | Post-prototype |
| Q-VIS-3 | Wave turbulence driven by flux feels right but needs tuning — attack too slow? | Design | First prototype session |
| Q-VIS-4 | Three.js not used in v1 WaveRenderer (pure canvas 2D). Add Three.js when moving to 3D effects or shaders. | Engineering | When needed |

---

*Document owner: Architecture team + Design — update as visual language evolves.*
