# Task — Build the Garden scene (SDD-010)

Read `CLAUDE.md` then `engineering/design/SDD-010-garden-scene.md`
completely before writing a single line of code. Also read
`docs/proto/PITCH-NOTES.md` for pitch curve remapping guidance.

---

## Scope

This task is entirely within `docs/proto/src/`. Do not touch the Python
pipeline, `src/` (Python), or any test files.

---

## What to build

### 1. Scene system refactor

Introduce a `SceneManager` and `Scene` abstraction so the existing
waveform renderer and the new garden renderer are both scenes.

**New files:**
- `docs/proto/src/scenes/base.ts` — Scene abstract class
- `docs/proto/src/sceneManager.ts` — SceneManager + swipe + dots

**Refactor:**
- Move existing wave rendering into `docs/proto/src/scenes/waveScene.ts`
  implementing the Scene interface
- `main.ts` creates a SceneManager with [WaveScene, GardenScene], handles
  the rAF loop, passes frames to the active scene

### 2. Swipe / click navigation

Implement on the canvas element (see SDD-010 §7):
- Touch swipe left/right (threshold: 50px)
- Mouse drag left/right (threshold: 50px)
- Dot indicators: fixed position bottom-centre, one per scene
- Active dot filled Gold (`#C9A96E`), inactive dots outlined Violet (`#7B5EA7`)
- CSS transition on scene switch: translate X, 300ms ease

### 3. Shared utilities

Create `docs/proto/src/utils.ts` with: `remap`, `remapPitch`, `lerp`,
`hexToRgba`, `hsl` (see SDD-010 §5 for exact implementations).

### 4. Garden scene — six organisms

Create `docs/proto/src/scenes/gardenScene.ts` as the orchestrator.
Create one file per organism in `docs/proto/src/scenes/garden/`:

```
frog.ts       — Frog's throat (drums)
snail.ts      — Snail (bass)
butterfly.ts  — Butterfly (vocals)
bees.ts       — Bees (other)
daffodil.ts   — Daffodils (piano)
dragonfly.ts  — Dragonfly (guitar)
```

Each organism file exports a class with:
```typescript
class FrogOrganism {
  constructor(canvas: HTMLCanvasElement) {}
  render(frame: StemFrame, ctx: CanvasRenderingContext2D, elapsed: number): void {}
}
```

Implement each organism exactly per SDD-010 §4. Key points:

**Frog:** throat sac inflates on onset, uses canvas arcs. Position: lower-right.

**Snail:** moves left→right, wraps. Speed from energy. Spiral shell drawn
with canvas arc. Trail effect optional.

**Butterfly:** bezier wing curves, color from pitch (violet→gold hue range),
figure-8 flight path, wings fold when unvoiced (pitch=0).

**Bees:** 8–16 bees orbiting a swarm centre, scatter on onset.
Use `frame.onset` from the `other` stem.

**Daffodils:** 3 flowers, 6 petals each drawn as ellipses. Petal length
from remapped piano pitch. Sway from energy.

**Dragonfly:** darts to random position on onset, hovers otherwise.
Four elongated wings at 45° angles. Trail on dart.

### 5. Garden environment

Draw in `gardenScene.ts` before rendering organisms. Layers in order
(back to front):

**Sky gradient:**
```typescript
const skyGrad = ctx.createLinearGradient(0, 0, 0, groundY);
skyGrad.addColorStop(0, '#06060A');      // Void at top
skyGrad.addColorStop(1, '#1A1428');      // Dusk at horizon
ctx.fillStyle = skyGrad;
ctx.fillRect(0, 0, canvas.width, groundY);
```

**Ground:**
```typescript
const groundGrad = ctx.createLinearGradient(0, groundY, 0, canvas.height);
groundGrad.addColorStop(0, '#1A1428');   // Dusk at surface
groundGrad.addColorStop(1, '#0E0B18');   // Deep at bottom
ctx.fillStyle = groundGrad;
ctx.fillRect(0, groundY, canvas.width, canvas.height - groundY);
```

**Atmospheric foliage (static):**
3 soft elliptical blobs, `rgba(123, 94, 167, 0.04)` (Violet, nearly
invisible), positioned at left/centre/right of the horizon. Large radii
(200–400px), Gaussian-blurred feel via `shadowBlur`.

**Ground line:**
1px rule at `groundY`, `rgba(164, 132, 200, 0.08)`.

**Fireflies (animated, music-independent):**
5 small gold points (`#C9A96E`, radius 2px) drifting slowly on independent
sine-wave paths. Opacity pulses gently between 0.3 and 0.9 at different
phases. They exist in the background layer, drawn before organisms.

```typescript
fireflies.forEach((f, i) => {
  f.x += Math.sin(elapsed * 0.3 + i) * 0.4;
  f.y += Math.cos(elapsed * 0.2 + i * 1.3) * 0.3;
  const opacity = 0.3 + 0.6 * (0.5 + 0.5 * Math.sin(elapsed * 0.7 + i * 2));
  ctx.beginPath();
  ctx.arc(f.x, f.y, 2, 0, Math.PI * 2);
  ctx.fillStyle = hexToRgba('#C9A96E', opacity);
  ctx.fill();
});
```

**Organism size:**
All organisms should be drawn at approximately 3x the size that feels
natural for a small canvas. These are the stars of the scene — they
should fill space and command attention.

### 6. Update `main.ts`

- Import SceneManager, WaveScene, GardenScene
- Create `sceneManager = new SceneManager(canvas, [waveScene, gardenScene])`
- rAF loop calls `sceneManager.render(frames, elapsed)` instead of
  calling the wave renderer directly
- Remove any direct renderer references

---

## Acceptance criteria

- `npm run build` succeeds with zero TypeScript errors
- `npm run dev` serves the prototype at localhost:5173
- Swiping left/right switches between waveform and garden scenes
- Clicking dots switches scenes
- Works on mobile (touch swipe)
- All six garden organisms are visible and react to music
- Butterfly color shifts with vocal pitch
- Frog throat inflates on drum beats
- Dragonfly darts on guitar onsets
- Daffodils bloom with piano pitch
- Scene transition is smooth (CSS translate, not instant jump)
- Existing waveform scene is unchanged and still works

---

## Notes

- Use canvas 2D throughout — no Three.js needed for v1
- Keep organism drawing code simple — elegant is better than photorealistic
- The garden should feel alive and reactive, not technically impressive
- If an organism's drawing is too complex, simplify — a suggestion of a
  butterfly is better than a broken one
- `docs/proto/PITCH-NOTES.md` has the per-stem pitch remapping ranges —
  use them

Do not modify the Python pipeline. Do not modify existing test files.
Do not modify `engineering/` docs — housekeeping is not required for this task.
