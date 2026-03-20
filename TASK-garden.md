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

Draw in `gardenScene.ts` before rendering organisms:
- Background: `#06060A`
- Ground line at 70% canvas height: subtle horizontal rule,
  `rgba(164, 132, 200, 0.08)`, 1px
- No other environment elements in v1

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
