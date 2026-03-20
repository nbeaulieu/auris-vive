# Auris Vive — Claude Code context

Read this file before doing anything. It is the source of truth for project
conventions, architecture, and current build state.

---

## What this project is

Auris Vive is a real-time music intelligence and visualisation platform. AI
separates any audio stream into its constituent instruments, transcribes every
note, and renders living generative visuals — simultaneously, in sync.

Tagline: *"The music was always this alive."*

---

## Who you are working for

The project owner is an experienced engineer (33 years SWE, university
professor). Do not over-explain. Do not add padding. Write production-quality
code with inline comments where non-obvious. Peer-level tone.

---

## Repository structure

```
auris-vive/
├── CLAUDE.md                   ← you are here
├── conftest.py                 ← pytest sys.path shim
├── pyproject.toml              ← deps, pytest config
├── scripts/                   ← bash scripts for dev workflows
├── test_audio/                ← local audio test files (gitignored)
├── brand/                     ← design identity (do not touch)
├── engineering/
│   ├── README.md              ← document map — UPDATE when adding ADRs/SDDs
│   ├── decisions/             ← ADR-001 through ADR-006
│   └── design/                ← SDD-001 through SDD-003
└── src/
    └── pipeline/
        ├── ingest.py          ✅ implemented
        ├── separate.py        ✅ implemented
        ├── transcribe.py      ✅ implemented
        ├── outputs.py         ✅ implemented
        ├── runner.py          ✅ implemented
        ├── analyse/
        │   ├── __init__.py    ✅ exports
        │   ├── curves.py      ✅ StemCurves + AnalyseError
        │   ├── analyse.py     ✅ analyse()
        │   ├── source.py      ✅ CurvesSource ABC
        │   ├── disk.py        ✅ DiskCurvesSource
        │   └── memory.py      ✅ MemoryCurvesSource
        └── drums/
            ├── base.py        ✅ DrumTranscriber ABC
            ├── onset.py       ✅ OnsetTranscriber (v1)
            └── adtlib.py      ✅ ADTLibTranscriber (stub)
```

---

## Two Python environments

| Environment | Python | Purpose | Activate |
|-------------|--------|---------|----------|
| `.venv` | 3.13 | ingest, API, non-ML tests | `source .venv/bin/activate` |
| `.venv-ml` | 3.11 | full ML stack incl. Basic Pitch, Demucs | `source .venv-ml/bin/activate` |

**Always use `.venv-ml` for any work involving Basic Pitch, pretty_midi, or
running the full pipeline.**

Run tests with:
```bash
./scripts/test-all.sh    # both environments
./scripts/test-base.sh   # .venv only
./scripts/test-ml.sh     # .venv-ml only
```

Tests must pass in both environments before committing.

---

## Critical import rule

`src/pipeline/__init__.py` is intentionally a docstring only — no imports.
This prevents eager-loading the full ML dependency chain. Always import
directly from submodules:

```python
# correct
from src.pipeline.transcribe import transcribe, TranscribeError

# wrong — triggers full chain including pretty_midi, demucs, etc.
from src.pipeline import transcribe
```

Any module that imports `pretty_midi`, `demucs`, or `basic_pitch` at the
module level must guard it under `TYPE_CHECKING`:

```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    import pretty_midi
```

This is a hard rule. Test failures from `ModuleNotFoundError: No module named
'pretty_midi'` in `.venv` mean this rule was violated.

---

## Pipeline data contracts

```
ingest      → np.ndarray  shape=(2, N)  dtype=float32  sr=44100  values∈[-1,1]
separate    → dict[str, np.ndarray]  keys: drums|bass|vocals|other|piano|guitar
transcribe  → dict[str, PrettyMIDI]  same keys as separate output
outputs     → OutputPaths  (written files, all paths absolute)
```

Each stage receives exactly one upstream type and returns exactly one
downstream type. No stage reaches past its immediate neighbour.

---

## Drum stem routing

Drums must NOT go through Basic Pitch — Basic Pitch is a pitch estimator and
drums are unpitched. The transcribe stage must route the drum stem through
`OnsetTranscriber` instead:

```python
from src.pipeline.drums import OnsetTranscriber

# in transcribe():
if stem_name == "drums":
    midi[stem_name] = OnsetTranscriber().transcribe(stem)
else:
    midi[stem_name] = _transcribe_with_basic_pitch(stem)
```

This is decided in ADR-003. Do not re-open this decision.

---

## Code conventions

- All domain exceptions inherit from a stage-specific error class
  (`TranscribeError`, `OutputError`, etc.) — never let library exceptions
  escape the module boundary
- Every public function has a docstring with Parameters / Returns / Raises
- Inline comments explain *why*, not *what*
- No print statements — use `logging.getLogger(__name__)`
- `TYPE_CHECKING` guard for any ML library import at module level
- Tests mock ML dependencies so the suite runs in both envs
- Follow the pattern in `ingest.py` and `separate.py` exactly

---

## Testing conventions

- Test files live in `tests/pipeline/`, `tests/adapters/`, `tests/api/`
- Tests that require `pretty_midi` use `@requires_pretty_midi` skip marker
- Tests that require `demucs` use `@requires_demucs` skip marker
- All demucs/basic_pitch calls are mocked — no model weights needed in tests
- Test naming: `TC-TRX-001` through `TC-TRX-NNN` for transcribe stage
- Each test file starts with a coverage map comment

---

## Document update rules

When you add or complete implementation work, you MUST update:

1. `engineering/README.md` — change 🔲 Pending to ✅ Written for any SDD/ADR
   you write, and add links
2. `engineering/design/SDD-001-pipeline-overview.html` — close any open
   questions that your work resolves; update the pipeline status section
3. `engineering/PROJECT-CONTEXT.md` — update the document inventory table

Do not skip these updates. Stale documentation is a bug.

---

## Current build state

| Component | Status | Notes |
|-----------|--------|-------|
| `src/pipeline/ingest.py` | ✅ Complete | 54 tests passing |
| `src/pipeline/separate.py` | ✅ Complete | 18 tests, runs on real audio |
| `src/pipeline/drums/` | ✅ Complete | OnsetTranscriber working |
| `src/pipeline/transcribe.py` | ✅ Complete | 10 tests passing |
| `src/pipeline/outputs.py` | ✅ Complete | 7 tests passing |
| `src/pipeline/analyse/` | ✅ Complete | 17 tests passing, includes pitch_curve |
| `src/pipeline/runner.py` | ✅ Complete | wires all stages |
| `docs/proto/` | ✅ Complete | TypeScript Vite app, deploys to GitHub Pages |
| `src/api/` | 🔲 Stub | blocked on Q-API-1, do not touch |
| `tests/pipeline/test_transcribe.py` | ✅ Complete | TC-TRX-001 through TC-TRX-009 |
| `tests/pipeline/test_outputs.py` | ✅ Complete | TC-OUT-001 through TC-OUT-007 |

---

## References

- `engineering/decisions/ADR-001-stack.md` — technology choices and rationale
- `engineering/decisions/ADR-002-inference-backend.md` — Modal, device selection
- `engineering/decisions/ADR-003-drum-transcription.md` — drum routing decision
- `engineering/design/SDD-002-ingest-stage.md` — reference implementation pattern
- `engineering/design/SDD-003-separate-stage.md` — parallel model pattern
- `src/pipeline/ingest.py` — reference for error handling and logging patterns
- `src/pipeline/separate.py` — reference for ML dependency mocking pattern
