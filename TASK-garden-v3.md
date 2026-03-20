# Task — Garden v3: psychedelic mushrooms + stem audio muting

Read `CLAUDE.md` before starting. Extends the existing garden scene.
Do not rewrite what works — replace roots with mushrooms and add audio muting.

Scope: `docs/proto/src/` and `scripts/export-curves.py` only.

---

## 1. Replace roots with psychedelic mushrooms (bass)

**Remove:** `docs/proto/src/scenes/garden/roots.ts` and all references.
**Create:** `docs/proto/src/scenes/garden/mushrooms.ts`

### Appearance

A cluster of 4–5 mushrooms of varying heights, positioned left-of-centre
on the ground line.

Each mushroom:
- **Stem:** thick rounded rectangle, slight wobble (slow sine wave, unique
  phase per mushroom). Color: off-white `#E8E0D5` (Pearl), slightly warm.
- **Cap:** large rounded amanita shape — flat bottom, domed top. Drawn as
  a filled arc/bezier. Width 1.5–2.5x the stem width.
- **Spots:** 3–5 white ellipses scattered across the cap surface, scale
  with cap size.
- **Bioluminescent ring:** soft glowing ellipse under the cap edge.
  `shadowBlur` driven by energy.

### Animation — driven by bass curves

**`energy` → cap pulse:**
Cap radius breathes: `capRadius = baseRadius * (1 + frame.energy * 0.4)`
All caps pulse together — the whole cluster breathes as one.

**`energy` → glow intensity:**
`shadowBlur = frame.energy * 60`
`shadowColor` shifts with pitch (see color below).

**`pitch_curve` → color:**
Bass pitch is in range 0.01–0.07. Remap to [0, 1] using `remapPitch(value, 0.01, 0.07)`.

```typescript
const pitchNorm = remapPitch(frame.pitch_curve, 0.01, 0.07);
const hue = 260 + pitchNorm * 120;  // violet(260) → teal(380)
const capColor = hsl(hue, 80, 30 + frame.energy * 40);
const glowColor = hsl(hue, 100, 60);
```

Low bass note = deep violet cap, higher bass note = electric teal/blue.
At peak energy the caps are vivid and saturated. At silence they are dark
and still.

**Stem sway:**
```typescript
const sway = Math.sin(elapsed * 0.8 + mushroom.phase) * 3 * frame.energy;
```

**At silence:** caps shrink to base size, glow disappears, color goes dark.
Apply the standard silence fade/freeze pattern from garden v2.

### Sizing
Mushrooms should be large — tallest mushroom ~25% of canvas height.
Cap widths 60–120px. This is bass — it should have visual weight.

### Position
Clustered left-of-centre, staggered depths (vary y slightly for overlap).
Tallest mushroom at back, shortest at front.

---

## 2. Stem audio muting via Web Audio API

### Overview

Instead of playing a single mixed MP3, load all 6 stem MP3s and play them
in perfect sync. Each stem has its own GainNode — toggling a pill sets
gain to 0 (mute) or 1 (unmute). The toggle is now both visual AND audio.

### Export: convert stems to MP3

In `scripts/export-curves.py`, for each song that has stems on disk,
convert each stem FLAC to MP3 and copy to `docs/proto/public/data/<slug>/stems/`:

```python
STEM_NAMES = ("drums", "bass", "vocals", "other", "piano", "guitar")

stems_out_dir = proto_data / slug / "stems"
stems_out_dir.mkdir(exist_ok=True)

for stem_name in STEM_NAMES:
    flac_path = test_audio / slug / "stems" / f"{stem_name}.flac"
    mp3_path  = stems_out_dir / f"{stem_name}.mp3"
    if flac_path.exists() and not mp3_path.exists():
        subprocess.run([
            "ffmpeg", "-y", "-i", str(flac_path),
            "-codec:a", "libmp3lame", "-qscale:a", "2",
            str(mp3_path)
        ], check=True, capture_output=True)
```

Also write a `stems_available: true` flag in `curves.json` when stems
are exported, so the browser knows whether to attempt stem playback.

### Audio engine refactor: `docs/proto/src/audio.ts`

Extend `AudioEngine` to support both modes:

**Mode A — single mix (existing behaviour, fallback):**
Plays `audio.mp3` as before. Used when stem MP3s are not available.

**Mode B — multi-stem (new):**
Loads all 6 stem MP3s, starts them simultaneously, routes each through
a GainNode.

```typescript
class AudioEngine {
  // existing single-track API preserved
  async loadStems(baseUrl: string, stemNames: string[]): Promise<void>
  setStemGain(stemName: string, gain: number): void  // 0 = mute, 1 = unmute
  get mode(): 'mix' | 'stems'
}
```

**Sync strategy:** decode all stem buffers before starting any. Start all
`AudioBufferSourceNode`s at `ctx.currentTime + 0.1` (100ms buffer to
ensure simultaneous start). `currentTime` continues to use the first stem
as the clock source.

**Fallback:** if any stem fails to load, fall back to mix mode silently
and log a warning.

### Toggle integration

When a stem pill is toggled:
1. Flip `stemEnabled[stemName]`
2. Call `audioEngine.setStemGain(stemName, enabled ? 1 : 0)`
3. The organism fades/freezes as before (existing silence behaviour handles it)

In mix mode, `setStemGain` is a no-op — visual toggle still works, audio
toggle is unavailable. No error, no UI change needed.

---

## 3. Update `curves.json` index

In `export-curves.py`, add `stems_available` to the per-song entry in
`index.json`:

```json
{
  "slug": "tswift",
  "name": "Fate of Ophelia — Taylor Swift",
  "stems_available": true
}
```

---

## Acceptance criteria

- `npm run build` zero TypeScript errors
- Bass organism is now a mushroom cluster — large caps, glowing, color-shifting
- Mushroom caps pulse with bass energy
- Mushroom color shifts from violet to teal with bass pitch
- Stems sway gently, independently
- Silence fade/freeze applies to mushrooms as with all other organisms
- `export-curves.py` exports stem MP3s to `docs/proto/public/data/<slug>/stems/`
- Toggling a stem pill mutes/unmutes that stem's audio when in stems mode
- Single mix fallback works when stem MP3s not available
- All existing functionality (waveform scene, scene dots, CC, other organisms) unchanged
