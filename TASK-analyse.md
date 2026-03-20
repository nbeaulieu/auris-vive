# Task — Implement the analyse stage (SDD-008)

Read `CLAUDE.md` fully before starting. Then read
`engineering/design/SDD-008-analyse-stage.md` completely — the full
implementation is specified there including all code samples.

---

## What to build

A new pipeline stage: `src/pipeline/analyse/`

This stage sits after `separate` and extracts per-stem visualisation curves
from the separated waveforms. Each stem produces a `StemCurves` object with
six normalised time-series curves that the visual layer drives animations from.

---

## Directory structure to create

```
src/pipeline/analyse/
    __init__.py      — exports StemCurves, AnalyseError, analyse, CurvesSource
    curves.py        — StemCurves dataclass + AnalyseError
    analyse.py       — analyse() function (main implementation)
    source.py        — CurvesSource ABC
    disk.py          — DiskCurvesSource
    memory.py        — MemoryCurvesSource

tests/pipeline/
    test_analyse.py  — full test suite (TC-ANA-001 through TC-ANA-012)
```

---

## Implementation notes

The full implementation is in SDD-008 §8. Follow it exactly. Key points:

**No ML dependencies** — this stage uses only librosa, numpy, and scipy.
All imports are safe at module level (no `TYPE_CHECKING` guard needed).

**`scipy` needs adding to pyproject.toml** — add `"scipy>=1.10"` to the
base `dependencies` list (not `[ml]`). It's Python 3.13 compatible.

**`_apply_envelope` is the only loop** — everything else is vectorised numpy.
The envelope loop is unavoidable (each frame depends on the previous frame)
but runs fast enough on 100fps × 30s = 3000 frames.

**`StemCurves.at_fps()`** — implements decimation (stride slicing), not
interpolation. Upsampling is Q-ANA-2 and out of scope.

**`DiskCurvesSource`** — files go in `test_audio/<slug>/curves/` with the
naming convention `<stem>_<curve>.npy` and `<stem>_meta.json`. The `save()`
method creates the directory if it doesn't exist.

**`MemoryCurvesSource`** — simple dict wrapper. `save()` stores in memory,
`load()` retrieves, `exists()` checks the dict, `available_stems()` returns
the keys.

---

## Test suite notes

All tests use synthetic stems — `np.zeros`, `np.ones`, or sine waves.
No audio files, no Demucs, no Basic Pitch. The suite must run in both
`.venv` and `.venv-ml` with 0 failures and 0 errors.

The `@requires_pretty_midi` and `@requires_demucs` patterns are NOT needed
here — scipy and librosa are in base deps.

For TC-ANA-009 (DiskCurvesSource round-trip), use `tmp_path` pytest fixture.

---

## Script update: run-stems.sh

After the analyse stage is implemented, update `scripts/run-stems.sh` to
run analysis after separation and write curves to disk. Add to the
`on_ready` callback:

```python
from src.pipeline.analyse.analyse import analyse
from src.pipeline.analyse.disk import DiskCurvesSource

curves_dir = Path(f"test_audio/{name}/curves")
source = DiskCurvesSource(curves_dir)

# analyse stems as they arrive
stem_curves = analyse(stems)
for stem_name, curves in stem_curves.items():
    source.save(stem_name, curves)
    print(f"  ✓ curves: {stem_name}")
```

---

## Housekeeping tasks

1. **`engineering/README.md`** — add SDD-008 row:
   `| [SDD-008](./design/SDD-008-analyse-stage.md) | Analyse — per-stem curve extraction | ✅ Written |`

2. **`engineering/PROJECT-CONTEXT.md`** — add SDD-008 to document inventory

3. **`CLAUDE.md`** — add analyse stage to build state table:
   `| src/pipeline/analyse/ | ✅ Complete | 12 tests passing |`

4. **`pyproject.toml`** — add `"scipy>=1.10"` to base dependencies

---

## Acceptance criteria

- `./scripts/test-all.sh` passes with 0 failures in both environments
- `src/pipeline/analyse/__init__.py` exports: `StemCurves`, `AnalyseError`,
  `analyse`, `CurvesSource`, `DiskCurvesSource`, `MemoryCurvesSource`
- All six curves in every `StemCurves` are float32, shape `(T,)`, values
  in `[0.0, 1.0]`
- `DiskCurvesSource` round-trip test passes
- `run-stems.sh` writes curves to disk after separation
- All housekeeping completed
- No regressions in existing tests

Do not touch `src/api/` or anything outside the analyse stage and scripts.
