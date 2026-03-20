# SDD-010 — Garden scene renderer

| Field      | Value                                                          |
|------------|----------------------------------------------------------------|
| Status     | Draft                                                          |
| Date       | 2026-03-20                                                     |
| Relates to | SDD-009 (visual prototype), SDD-008 (analyse)                 |
| Covers     | Garden scene: six stem organisms + swipeable scene system     |

---

## 1. Purpose and scope

The Garden scene is the second visual scene in the prototype, accessible
by swiping or clicking alongside the existing waveform scene.

Each stem drives a distinct living organism in a shared garden environment.
The organisms respond to the music in real time via the pre-computed curve
data — no new pipeline work required.

**Stem → organism mapping:**

| Stem   | Organism         | Primary driver      | Secondary driver    |
|--------|-----------------|---------------------|---------------------|
| drums  | Frog's throat   | onset (pulse/inflate) | energy (size)     |
| bass   | Snail           | energy (speed)      | amplitude (shell glow) |
| vocals | Butterfly       | pitch_curve (color) | energy (wing speed) |
| other  | Bees            | energy (swarm density) | onset (scatter) |
| piano  | Daffodils       | pitch_curve (bloom) | energy (sway)      |
| guitar | Dragonfly       | onset (dart/speed)  | energy (wing blur) |

---

## 2. Scene system

### Navigation
- Swipe left/right on touch devices
- Click and drag on desktop
- Dot indicators at bottom centre — click a dot to jump to that scene
- Smooth CSS transition between scenes (translate X)

### Structure
```
SceneManager
  scenes: Scene[]        — ordered array, index = scene number
  currentIndex: number
  swipe(direction)       — animate transition, update dots
  goTo(index)            — jump directly

Scene (abstract)
  mount(canvas)          — called when scene becomes active
  unmount()              — called when scene leaves
  render(frames, elapsed) — called every rAF tick while active
```

### Dot indicator
Fixed position, bottom centre. One dot per scene. Active dot filled,
inactive dots outlined. Brand colours (Violet/Gold).

```html
<div class="scene-dots">
  <span class="dot active"></span>
  <span class="dot"></span>
</div>
```

---

## 3. Garden scene environment

### Canvas layout
Full viewport canvas, dark background (`#06060A` — Void).
The garden occupies the full canvas — no lanes, no divisions.
Organisms are positioned in a shared space:

```
┌─────────────────────────────────────┐
│  ·  dragonfly  ·  butterfly  ·      │  upper third — air
│     bees swarm                      │
├─────────────────────────────────────┤
│  daffodils  daffodils  daffodils    │  middle — flora
├─────────────────────────────────────┤
│  snail ──→           frog 🐸        │  ground — lower third
└─────────────────────────────────────┘
```

### Ground line
A subtle horizontal line at 70% canvas height. Frog and snail live below.
Daffodils straddle it. Butterfly, bees, dragonfly live above.

### Colour palette
Background: `#06060A` (Void)
Ground hint: `rgba(164, 132, 200, 0.08)` (Iris, very subtle)
Organisms use brand colours as base, shifted by curve values.

---

## 4. Organism specifications

### 4.1 Frog's throat (drums)

A simple frog silhouette sitting on the ground. Its throat sac inflates
and deflates with each drum onset.

- **Resting state:** small oval throat, frog body still
- **On onset:** throat sac rapidly inflates (scale 1.0 → 2.5) then slowly
  deflates over ~300ms
- **Energy:** overall frog size scales subtly with energy (1.0 → 1.3x)
- **Color:** deep green `#2D5A27`, throat sac glows Violet on onset

**Drawing:** SVG path or canvas arc. Frog body = two circles (body + head).
Throat sac = ellipse below head, scaled by onset value.

```javascript
// Throat inflation
const throatScale = 1.0 + frame.onset * 1.5;
ctx.ellipse(x, throatY, throatW * throatScale, throatH * throatScale, 0, 0, Math.PI * 2);
```

Position: lower-right quadrant, sitting on ground line.

---

### 4.2 Snail (bass)

A snail with a spiral shell, slowly moving left to right across the canvas.
When it reaches the right edge it wraps back to the left.

- **Speed:** proportional to bass energy — nearly still at silence,
  slowly crawling at peak
- **Shell:** spiral drawn with canvas arc. Shell glow (shadow blur)
  proportional to amplitude
- **Body:** soft ochre colour, stretches slightly with speed
- **Trail:** faint iridescent trail behind the snail, fades over 2 seconds

**Movement:**
```javascript
snailX += frame.energy * 0.8;  // pixels per frame at 60fps
if (snailX > canvas.width + 50) snailX = -50;
```

Position: ground level, y = groundY.

---

### 4.3 Butterfly (vocals)

The signature organism. A butterfly with two pairs of wings that flutter
with the vocals.

- **Wing speed:** proportional to energy — still when vocals are silent,
  rapidly flapping at peak
- **Color:** hue derived from pitch_curve using the remapping in PITCH-NOTES.md.
  Low pitch = cool blue/violet, high pitch = warm gold/amber
- **Iridescence:** wing opacity pulses gently, independent of music (slow
  breathing animation at 0.3Hz)
- **Position:** floats in upper-middle of canvas. Gentle figure-8 flight
  path driven by a Lissajous curve, speed proportional to energy
- **Voiced/unvoiced:** when pitch_curve = 0 (unvoiced), wings fold slowly.
  When voiced, wings spread.

**Wing drawing:** two filled bezier curves per wing pair, mirrored.
Wing shape is a classic butterfly silhouette — rounded upper wing,
pointed lower wing.

```javascript
// Color from pitch
const voiced = frame.pitch_curve > 0;
const hue = voiced
  ? 260 + remapPitch(frame.pitch_curve, 0.01, 0.93) * 100  // violet → gold
  : 260;  // resting violet
```

---

### 4.4 Bees (other)

A swarm of 8–12 small bees. Their swarm density and activity level is
driven by the `other` stem energy.

- **Count:** 8 bees at minimum energy, up to 16 at peak
- **Swarm centre:** drifts slowly around the upper-left quadrant
- **Individual movement:** each bee has its own small random orbit around
  the swarm centre. Orbit radius proportional to energy.
- **On onset:** bees briefly scatter outward, then regroup
- **Wings:** tiny ellipses, blur with speed
- **Color:** amber `#C9A96E` (Gold), darkens at low energy

**Bee state:**
```javascript
bees.forEach(bee => {
  bee.angle += 0.05 + frame.energy * 0.1;
  bee.r = 20 + frame.energy * 40 + (frame.onset * 60);
  bee.x = swarmCx + Math.cos(bee.angle) * bee.r;
  bee.y = swarmCy + Math.sin(bee.angle) * bee.r;
});
```

---

### 4.5 Daffodils (piano)

Three to five daffodils growing from the ground line. They bloom and sway
with the piano.

- **Bloom:** petal spread proportional to pitch_curve — closed bud at 0,
  fully open at 1. Use remapped piano pitch range.
- **Sway:** stems oscillate left/right, driven by energy. Amplitude of
  sway = energy * 15px
- **Color:** yellow `#FFD700` petals, white inner trumpet, green stem.
  Petals shift slightly warmer (toward Gold) at high pitch.
- **Count:** 3 daffodils, evenly spaced across the centre of the canvas

**Petal drawing:** 6 ellipse petals arranged in a circle around a central
trumpet circle, each petal rotated 60°. Petal length scales with pitch.

```javascript
const petalLength = 8 + remapPitch(frame.pitch_curve, 0.01, 0.8) * 25;
for (let i = 0; i < 6; i++) {
  const angle = (i / 6) * Math.PI * 2;
  // draw ellipse at angle, length = petalLength
}
```

Position: ground line, centre canvas.

---

### 4.6 Dragonfly (guitar)

A dragonfly that darts around the upper canvas. Fast, precise movements
triggered by guitar onsets.

- **Dart:** on onset, dragonfly instantly jumps to a new random position
  in the upper canvas. The jump distance is proportional to onset strength.
- **Hover:** between onsets, dragonfly hovers with small vibration
  (± 2px random walk per frame)
- **Wings:** four elongated ellipses at 45° angles. Wing blur (shadow)
  proportional to energy — still wings at low energy, blurred at high
- **Color:** iridescent teal `#00CED1`, wings semi-transparent
- **Trail:** brief motion blur trail on dart (3 ghost positions at
  decreasing opacity)

```javascript
if (frame.onset > 0.3) {
  // dart to new position
  const dartDist = frame.onset * 200;
  const angle = Math.random() * Math.PI * 2;
  dragonfly.targetX = dragonfly.x + Math.cos(angle) * dartDist;
  dragonfly.targetY = dragonfly.y + Math.sin(angle) * dartDist;
}
// ease toward target
dragonfly.x += (dragonfly.targetX - dragonfly.x) * 0.3;
dragonfly.y += (dragonfly.targetY - dragonfly.y) * 0.3;
```

Position: upper third, starts centre-right.

---

## 5. Shared rendering utilities

Add to `src/utils.ts`:

```typescript
// Remap a value from one range to another, clamped to [0, 1]
export function remap(value: number, inMin: number, inMax: number): number {
  return Math.max(0, Math.min(1, (value - inMin) / (inMax - inMin)));
}

// Remap pitch curve accounting for per-stem ranges
export function remapPitch(value: number, stemMin = 0.01, stemMax = 0.25): number {
  if (value === 0) return 0;
  return remap(value, stemMin, stemMax);
}

// Linear interpolation
export function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

// Hex colour to rgba string
export function hexToRgba(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

// HSL colour string
export function hsl(h: number, s: number, l: number, a = 1): string {
  return `hsla(${h},${s}%,${l}%,${a})`;
}
```

---

## 6. File structure

```
docs/proto/src/
  scenes/
    base.ts          — Scene abstract class
    waveScene.ts     — existing WaveRenderer refactored as a Scene
    gardenScene.ts   — GardenScene orchestrator
    garden/
      frog.ts
      snail.ts
      butterfly.ts
      bees.ts
      daffodil.ts
      dragonfly.ts
  sceneManager.ts    — SceneManager + swipe handling + dot indicators
  utils.ts           — remap, lerp, hexToRgba, hsl
```

---

## 7. Swipe / click implementation

```typescript
// Touch
canvas.addEventListener('touchstart', e => { touchStartX = e.touches[0].clientX; });
canvas.addEventListener('touchend', e => {
  const dx = e.changedTouches[0].clientX - touchStartX;
  if (Math.abs(dx) > 50) sceneManager.swipe(dx < 0 ? 'left' : 'right');
});

// Mouse drag
canvas.addEventListener('mousedown', e => { dragStartX = e.clientX; isDragging = true; });
canvas.addEventListener('mouseup', e => {
  if (!isDragging) return;
  const dx = e.clientX - dragStartX;
  if (Math.abs(dx) > 50) sceneManager.swipe(dx < 0 ? 'left' : 'right');
  isDragging = false;
});
```

---

## 8. Open questions

| ID | Question | Owner | Target |
|----|----------|-------|--------|
| Q-GAR-1 | Ground texture — bare dark void or subtle grass suggestion? | Design | First prototype session |
| Q-GAR-2 | Do organisms interact? (butterfly lands on daffodil?) | Design | Post-v1 |
| Q-GAR-3 | Day/night cycle driven by overall energy? | Design | Post-v1 |
| Q-GAR-4 | Mobile touch feel — does swipe feel right or should dots be larger? | Design | First phone test |

---

*Document owner: Design + Engineering — living document, update as organisms evolve.*
