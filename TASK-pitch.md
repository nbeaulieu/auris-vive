# Task — Add pitch extraction to the analyse stage

Read `CLAUDE.md` fully before starting.

---

## Context

The analyse stage (`src/pipeline/analyse/`) already extracts six curves
per stem: `energy`, `brightness`, `onset`, `warmth`, `texture`, `flux`.
These are defined in `src/pipeline/analyse/curves.py` as fields on
`StemCurves`.

Pitch (`pitch_curve`) is the missing piece. It unlocks visual parameters
like `petal_color = f(vocals_pitch)` and `branch_sway = f(bass_pitch)`.

---

## What to add

### 1. `pitch_curve` field on `StemCurves`

Add one new field to the `StemCurves` dataclass in `curves.py`:

```python
pitch_curve: np.ndarray   # fundamental frequency, normalised ∈ [0, 1]
                          # 0.0 = unvoiced/unpitched, >0 = pitched content
```

Same shape as all other curves: `(T,)`, `float32`, values in `[0.0, 1.0]`.

Unvoiced frames (where no pitch is detected) must be `0.0`, not NaN.

### 2. Pitch extraction in `analyse.py`

Use `librosa.pyin` for pitch tracking. `pyin` is the best available
monophonic pitch estimator in librosa — it handles voiced/unvoiced
detection natively and returns `NaN` for unvoiced frames.

```python
f0, voiced_flag, voiced_probs = librosa.pyin(
    mono_stem,
    fmin=librosa.note_to_hz('C2'),   # ~65 Hz — below bass guitar low E
    fmax=librosa.note_to_hz('C7'),   # ~2093 Hz — above soprano vocal range
    sr=sr,
    hop_length=hop,
    fill_unvoiced_with=np.nan,
)
```

Post-processing:
1. Replace `NaN` with `0.0` (unvoiced = silence in the visual layer)
2. Normalise voiced frames: divide by `fmax` (`librosa.note_to_hz('C7')`)
   so the curve is in `[0.0, 1.0]`
3. Apply the same envelope shaping (attack/release/smoothing) as other curves

**Per-stem pitch strategy** — only some stems benefit from pitch extraction:

| Stem   | Extract pitch? | Rationale |
|--------|---------------|-----------|
| vocals | Yes           | Primary melodic use case |
| bass   | Yes           | Bass line pitch drives weight/gravity visuals |
| piano  | Yes           | Melodic stem |
| guitar | Yes           | Melodic stem |
| other  | Yes           | May contain melodic content |
| drums  | No            | Unpitched — pyin on drums is meaningless noise |

For drums, set `pitch_curve = np.zeros(n_frames, dtype=np.float32)`.

### 3. `at_fps()` method update

`StemCurves.at_fps()` must decimate `pitch_curve` alongside the other
curves. Update the `dataclasses.replace()` call to include it.

### 4. `DiskCurvesSource` update

`save()` and `load()` must handle `pitch_curve` the same as other curves:
- Save: `np.save(dir / f"{stem_name}_pitch_curve.npy", curves.pitch_curve)`
- Load: read it back, default to zeros array if file missing (backward
  compatibility with existing curves on disk)

### 5. `export-curves.py` update

The JSON export must include `pitch_curve` in the stem data:

```json
{
  "stems": {
    "vocals": {
      "energy":      [...],
      "brightness":  [...],
      "onset":       [...],
      "warmth":      [...],
      "texture":     [...],
      "flux":        [...],
      "pitch_curve": [...]   ← add this
    }
  }
}
```

---

## Test suite updates

Update `tests/pipeline/test_analyse.py`:

- TC-ANA-002 (all curves same shape) — add `pitch_curve` to the check
- TC-ANA-003 (all values in [0,1]) — add `pitch_curve` to the check
- TC-ANA-004 (dtype float32) — add `pitch_curve` to the check
- TC-ANA-013 (new): drums stem → `pitch_curve` is all zeros
- TC-ANA-014 (new): vocals stem with sine wave → `pitch_curve` has
  non-zero values in voiced frames
- TC-ANA-015 (new): `at_fps()` decimates `pitch_curve` correctly
- TC-ANA-016 (new): `DiskCurvesSource` round-trip preserves `pitch_curve`
- TC-ANA-017 (new): loading old curves without `pitch_curve.npy` returns
  zeros array (backward compatibility)

---

## Performance note

`librosa.pyin` is significantly slower than the other feature extractors —
it runs a probabilistic YIN algorithm and can take 1-3 seconds per stem.
For 6 stems that's 6-18 seconds of analysis time, which is acceptable for
batch processing but worth logging so it's visible.

Log at INFO level:
```python
logger.info("pitch extraction: %s  (%.1fs)", stem_name, elapsed)
```

---

## Housekeeping

1. Update `engineering/design/SDD-008-analyse-stage.md`:
   - Add `pitch_curve` to the StemCurves contract table in §3
   - Add pitch extraction description to §4
   - Add TC-ANA-013 through TC-ANA-017 to §9
   - Close Q-ANA-1 partially — pitch extraction is now available

2. Update `CLAUDE.md` build state — analyse stage now has pitch

---

## Acceptance criteria

- `./scripts/test-all.sh` passes with 0 failures in both environments
- `StemCurves` has `pitch_curve` field, shape `(T,)`, float32, `[0, 1]`
- Drums pitch curve is all zeros
- Non-drum pitch curve has non-zero values on a sine wave input
- `DiskCurvesSource` round-trip works including backward compatibility
- `export-curves.py` includes `pitch_curve` in JSON output
- `at_fps()` decimates `pitch_curve` correctly
- Performance logging in place

Do not touch `src/api/`, `docs/proto/`, or any other pipeline stage.
Scope is strictly `src/pipeline/analyse/` and its tests.
