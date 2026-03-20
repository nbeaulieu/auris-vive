# Task — Build the visual prototype (SDD-009)

Read `CLAUDE.md` then `engineering/design/SDD-009-visual-prototype.md`
completely before writing a single line of code.

---

## What to build

A static web prototype that plays audio and renders six stem waves
simultaneously on one canvas, driven by pre-computed curve data.

Two deliverables:

1. **`scripts/export-curves.py`** — Python script that converts `.npy`
   curve files to a JSON bundle the browser can load
2. **`docs/proto/`** — TypeScript/Vite app with audio playback and
   canvas-based wave renderer

---

## Part 1: export-curves.py

### Location
`scripts/export-curves.py`

### What it does
Reads every song in `test_audio/songs.json` that has curves on disk
(`test_audio/<slug>/curves/`) and exports to `docs/proto/data/<slug>/`.

### Output per song
- `curves.json` — all curves, rounded to 2dp (see SDD-009 §3 for exact format)
- `audio.wav` — copied from `test_audio/<slug>/clip.wav`

### Skip logic
Skip songs that have no curves directory. Print a clear message for each
song processed and each song skipped.

### Run from repo root
```bash
source .venv-ml/bin/activate
python3 scripts/export-curves.py
```

---

## Part 2: docs/proto/ TypeScript app

### Directory structure
```
docs/proto/
  index.html
  package.json
  tsconfig.json
  vite.config.ts
  src/
    main.ts
    audio.ts
    curvePlayer.ts
    renderer.ts
    renderers/
      base.ts
      wave.ts
    palette.ts
    types.ts
  data/            ← populated by export-curves.py, gitignored
```

### Implement exactly as specified in SDD-009
- `types.ts` — StemName, StemFrame, CurvesData (§4)
- `palette.ts` — STEM_COLOURS, BACKGROUND (§9)
- `audio.ts` — AudioEngine class (§5)
- `curvePlayer.ts` — CurvePlayer class (§6)
- `renderers/base.ts` — StemRenderer abstract class, CanvasLane (§7)
- `renderer.ts` — CanvasRenderer orchestrator (§7)
- `renderers/wave.ts` — WaveRenderer (§8)

### `main.ts` responsibilities
- On load: fetch `data/<slug>/curves.json`, instantiate AudioEngine,
  CurvePlayer, and CanvasRenderer with one WaveRenderer per stem
- Song selector: a `<select>` dropdown populated from available slugs
  in `data/`. Changing song reloads curves + audio.
- Play/pause button: toggles AudioEngine
- `requestAnimationFrame` loop: calls `curvePlayer.frameAt(audio.currentTime)`,
  passes result to `canvasRenderer.render(frames, elapsed)`
- Canvas fills the viewport, black background

### `index.html`
Minimal. Dark background (`#06060A`). Canvas fills viewport.
Controls (play/pause + song selector) overlaid bottom-centre in
Jost font, subtle styling consistent with Auris Vive brand.
No frameworks — vanilla HTML + the compiled TS bundle.

### Audio note
Browser autoplay policy requires a user gesture before AudioContext
can start. The play button click IS the gesture — no workaround needed.
Show a "click to play" prompt on load.

---

## Part 3: .gitignore updates

Add to `.gitignore`:
```
# Proto data (generated — do not commit audio or curve JSON)
docs/proto/data/
docs/proto/node_modules/
docs/proto/dist/
```

The `docs/proto/` source code IS committed. The `data/` directory is
local only — each developer runs `export-curves.py` to populate it.

---

## Part 4: README in docs/proto/

Write a short `README.md` explaining:
1. `npm install`
2. `python3 scripts/export-curves.py` (from repo root, .venv-ml active)
3. `npm run dev`
4. Open `http://localhost:5173`

---

## Housekeeping

1. **`engineering/README.md`** — add SDD-009:
   `| [SDD-009](./design/SDD-009-visual-prototype.md) | Visual prototype — web audio + wave renderer | ✅ Written |`

2. **`engineering/PROJECT-CONTEXT.md`** — add SDD-009 to document inventory

3. **`CLAUDE.md`** — add to build state:
   `| docs/proto/ | ✅ Complete | TypeScript Vite app, deploys to GitHub Pages |`

---

## Acceptance criteria

- `python3 scripts/export-curves.py` runs without error for any song
  that has curves on disk
- `cd docs/proto && npm install && npm run build` succeeds with no
  TypeScript errors
- `npm run dev` serves a working prototype at localhost:5173
- Audio plays when play button is clicked
- Six waves render simultaneously on one canvas
- Waves visibly react to the music (amplitude and turbulence change)
- Song selector works — changing song reloads audio and curves
- `.gitignore` updated — `data/`, `node_modules/`, `dist/` not committed
- All housekeeping completed

Do not touch `src/` Python pipeline code. Do not touch existing tests.
This task is entirely in `scripts/export-curves.py` and `docs/proto/`.
