# Task — Garden scene follow-up (v2)

Read `CLAUDE.md` before starting. This task builds on the garden scene
already implemented. Do not rewrite what works — extend it.

Scope: `docs/proto/src/` only. No Python pipeline changes.

---

## 1. Replace snail with roots (bass)

The snail is too small and subtle for bass. Replace it with **roots** —
thick organic roots that grow upward from the bottom edge of the canvas,
driven by bass amplitude.

**Remove:** `docs/proto/src/scenes/garden/snail.ts` and all references.

**Create:** `docs/proto/src/scenes/garden/roots.ts`

Roots behaviour:
- 4–6 thick root tendrils growing upward from the bottom of the canvas
- Each root is a bezier curve from the bottom edge, curving organically
- **Root height:** proportional to bass `energy` — roots retract to zero
  at silence, extend upward ~30% of canvas height at peak energy
- **Thickness:** stroke width 8–20px, proportional to energy
- **Color:** deep earthy brown `#3D2B1F`, glows softly with Iris
  `rgba(160, 132, 200, 0.4)` shadow at high energy
- **Movement:** each root has a slight independent sway (slow sine wave,
  different phase per root)
- **At silence:** roots retract fully to the ground line and disappear

```typescript
// Root growth
const rootHeight = frame.energy * canvas.height * 0.3;
// Draw bezier from (rootX, canvas.height) curving to (rootX + offset, canvas.height - rootHeight)
```

Position: distributed across the bottom of the canvas, 3 left, 3 right,
leaving centre clear for daffodils.

---

## 2. Stem toggle pills — global persistent UI

A horizontal row of pill buttons, one per stem, fixed at the bottom of
the viewport. Persistent across scene swipes — does not move when swiping
between scenes.

**Implementation:** DOM overlay, not canvas. A `<div class="stem-toggles">`
positioned fixed above the scene dots.

### Visual design
- Pill shape: `border-radius: 20px`, padding `6px 14px`
- Font: Jost, 11px, letter-spacing 0.1em, uppercase
- Active (stem enabled): filled with stem colour at 80% opacity, white text
- Inactive (stem disabled): transparent background, stem colour border,
  muted text
- Gap between pills: 8px
- On mobile: pills wrap if needed, or scroll horizontally

### Stem colours and labels
```typescript
const STEM_PILLS = [
  { stem: 'drums',  label: 'DRUMS',  color: '#7B5EA7' },
  { stem: 'bass',   label: 'BASS',   color: '#5B8A6E' },  // earthy green for roots
  { stem: 'vocals', label: 'VOCALS', color: '#C9A96E' },
  { stem: 'other',  label: 'OTHER',  color: '#A084C8' },
  { stem: 'piano',  label: 'PIANO',  color: '#FFD700' },
  { stem: 'guitar', label: 'GUITAR', color: '#00CED1' },
];
```

### State
`stemEnabled: Record<StemName, boolean>` — all true by default.
Toggling a pill flips the boolean.

### Passing state to scenes
The SceneManager receives `stemEnabled` and passes it to the active
scene's `render()` call:

```typescript
sceneManager.render(frames, elapsed, stemEnabled);
```

Each scene checks `stemEnabled[stemName]` before rendering that organism.

---

## 3. Silence behaviour — fade and freeze

When a stem's `energy` drops below `0.05` (silence threshold):

1. **Fade:** organism opacity smoothly drops to 0 over 500ms
2. **Freeze:** organism stops all movement — position and state locked
   at last active frame

When energy returns above threshold:
1. **Unfreeze:** movement resumes from frozen position
2. **Fade in:** opacity smoothly rises to 1 over 300ms (faster than fade out)

Implementation: each organism tracks `opacity` (smoothed toward 0 or 1)
and `frozen` boolean. All draw calls multiply by `opacity`.

```typescript
// In each organism's render():
const isSilent = frame.energy < 0.05;
this.opacity += isSilent
  ? Math.max(0, this.opacity - 0.033)   // fade out ~500ms at 60fps
  : Math.min(1, this.opacity + 0.05);   // fade in ~300ms at 60fps

if (isSilent && this.opacity < 0.01) {
  this.frozen = true;
  return;  // skip all updates
}
this.frozen = false;
```

Apply this pattern to ALL six organisms consistently.

---

## 4. CC overlay — Whisper transcription

### Python side: `scripts/transcribe-vocals.sh`

New script that runs Whisper on the vocal stem for a given song and
writes a timestamped transcript JSON.

```bash
#!/bin/bash
# Usage: ./scripts/transcribe-vocals.sh <slug>
# Requires: pip install openai-whisper (in .venv-ml)
# Output: test_audio/<slug>/transcript.json
```

```python
import whisper, json
from pathlib import Path

slug = sys.argv[1]
vocals_path = Path(f"test_audio/{slug}/stems/vocals.flac")
model = whisper.load_model("base")
result = model.transcribe(str(vocals_path), word_timestamps=True)

words = []
for segment in result["segments"]:
    for word in segment.get("words", []):
        words.append({
            "word":  word["word"].strip(),
            "start": round(word["start"], 3),
            "end":   round(word["end"], 3),
        })

output = {"slug": slug, "language": result["language"], "words": words}
Path(f"test_audio/{slug}/transcript.json").write_text(json.dumps(output, indent=2))
print(f"✓ {len(words)} words → test_audio/{slug}/transcript.json")
```

### Export side: `scripts/export-curves.py`

If `test_audio/<slug>/transcript.json` exists, copy it to
`docs/proto/public/data/<slug>/transcript.json`. If not, skip silently.

### JS side: CC overlay

**New file:** `docs/proto/src/ccOverlay.ts`

```typescript
export class CCOverlay {
  private words: {word: string, start: number, end: number}[] = [];
  private enabled = false;
  private el: HTMLElement;

  async load(url: string): Promise<void>  // fetch transcript.json, store words
  toggle(): void                           // show/hide overlay
  update(currentTime: number): void        // called each rAF tick
  // finds current word(s) by time, renders to DOM element
}
```

**Visual:** fixed position, bottom-centre above the stem pills. Large
Cormorant Garamond text, Pearl colour, subtle fade in/out per word.
Max 2–3 words visible at once. Gracefully absent if no transcript.json.

**Toggle button:** small `CC` button in the controls bar. Only visible
if transcript data is available for the current song.

---

## 5. Pipeline UI update

Add **t** action to `scripts/pipeline-ui.py`:
- **t** → transcribe vocals for a selected song (runs `transcribe-vocals.sh`)
- Add to **r** (run all) chain: grab → stems → analyse → transcribe → export

Also add `transcribe` column to the song table (✓ if `transcript.json` exists).

---

## Acceptance criteria

- `npm run build` zero TypeScript errors
- Bass organism is now roots, not snail — grows from bottom with energy
- Stem toggle pills visible at bottom, persist across scene swipes
- Toggling a pill immediately stops that organism rendering
- Organisms fade out and freeze at silence, fade in on return
- `./scripts/transcribe-vocals.sh tswift` produces `transcript.json`
- CC overlay shows synced lyrics when transcript available, hidden otherwise
- CC toggle button only appears when transcript exists
- All existing functionality unchanged
