# Task — Implement transcribe stage and outputs stage

Read `CLAUDE.md` fully before starting. Then read
`engineering/decisions/ADR-003-drum-transcription.md` and
`engineering/design/SDD-002-ingest-stage.md` (reference pattern).

---

## Primary task: implement `src/pipeline/transcribe.py`

Replace the current stub with a full production implementation.

### What it must do

Accept the separated stems dict from the separate stage and return a
`dict[str, PrettyMIDI]` with one MIDI object per stem.

**Drum stem:** route through `OnsetTranscriber` — never through Basic Pitch.
This is decided in ADR-003. The `DrumTranscriber` instance should be
injectable (default to `OnsetTranscriber()`) so tests can swap it.

**All other stems:** transcribe via Basic Pitch's `predict` function. Basic
Pitch accepts a file path, not a numpy array — write each stem to a temp WAV
file, run Basic Pitch, delete the temp file. Use `tempfile.NamedTemporaryFile`.

**Basic Pitch usage pattern:**
```python
from basic_pitch.inference import predict
from basic_pitch import ICASSP_2022_MODEL_PATH

model_output, midi_data, note_events = predict(
    audio_path,
    ICASSP_2022_MODEL_PATH,
)
# midi_data is a pretty_midi.PrettyMIDI object — return it directly
```

### Signature

```python
def transcribe(
    stems: dict[str, np.ndarray],
    sr: int = 44100,
    drum_transcriber: DrumTranscriber | None = None,
) -> dict[str, pretty_midi.PrettyMIDI]:
```

### Error handling

All failures raise `TranscribeError` with a descriptive message. The original
exception must be chained via `from exc`. Temp files must be cleaned up even
on failure — use try/finally.

### Test suite: `tests/pipeline/test_transcribe.py`

Write a full test suite. All Basic Pitch calls must be mocked — no model
weights needed. Follow the `@requires_pretty_midi` / `@requires_demucs`
pattern from `test_separate.py` and `test_drums.py`.

Minimum test cases:
- TC-TRX-001: valid 6-stem input → returns dict with all 6 keys
- TC-TRX-002: drum stem routed to DrumTranscriber, not Basic Pitch
- TC-TRX-003: non-drum stems call Basic Pitch predict
- TC-TRX-004: custom DrumTranscriber instance is used when provided
- TC-TRX-005: Basic Pitch failure → TranscribeError with __cause__ chained
- TC-TRX-006: temp files cleaned up on success
- TC-TRX-007: temp files cleaned up on failure
- TC-TRX-008: wrong input type → TranscribeError

---

## Secondary task: implement `src/pipeline/outputs.py`

Replace the stub with a working FLAC + MIDI writer.

### What it must do

Accept a `JobResult` (stems + midi dicts) and an output directory, write
all files, return an `OutputPaths` dataclass.

**FLAC stems:** use `soundfile.write()`. Stems are `(2, N)` channel-first —
soundfile expects `(N, 2)` channel-last, so transpose: `stem.T`.
Subtype: `PCM_24`.

**MIDI files:** use `midi_object.write(str(path))`.

**Score (MusicXML):** stub for now — set `score_xml=None` and `score_pdf=None`
in the returned `OutputPaths`. music21 score generation is SDD-005, not this task.

### Signature

The existing `JobResult` and `OutputPaths` dataclasses in `outputs.py` are
correct — do not change them. Just implement `write()`.

### Error handling

`OutputError` for any failure. If MIDI writing fails for one stem, it should
not prevent the FLAC files from being written — collect errors and raise at
the end if any occurred.

### Test suite: `tests/pipeline/test_outputs.py`

Write a full test suite using `tmp_path` pytest fixture for the output
directory. No audio processing needed — use synthetic numpy arrays.

Minimum test cases:
- TC-OUT-001: all 6 FLAC stems written to output_dir
- TC-OUT-002: all 6 MIDI files written to output_dir
- TC-OUT-003: returned OutputPaths contains correct absolute paths
- TC-OUT-004: FLAC files are readable by soundfile
- TC-OUT-005: MIDI files are readable by pretty_midi
- TC-OUT-006: output_dir does not exist → OutputError
- TC-OUT-007: score_xml and score_pdf are None (SDD-005 pending)

---

## Housekeeping tasks (do these after the code is green)

1. **`engineering/README.md`** — update SDD-004 and SDD-005 rows from
   🔲 Pending to ✅ Written, add links to the new SDD files

2. **`engineering/PROJECT-CONTEXT.md`** — update the document inventory
   table to reflect SDD-004 and SDD-005 as written

3. **`engineering/design/SDD-001-pipeline-overview.html`** — find the open
   questions section and close Q-TRX-2 (drum transcription resolved by ADR-003)
   and Q-SEP-1 (model loading resolved by ADR-002). Update pipeline stage
   status for transcribe and outputs from pending to implemented.

4. **`engineering/README.md` development setup section** — replace the stub
   with the actual setup commands:
   ```bash
   python3.11 -m venv .venv-ml
   source .venv-ml/bin/activate
   pip install -e ".[dev,ml]"
   # FFmpeg required for MP3/MP4 decoding
   brew install ffmpeg
   ```

---

## Acceptance criteria

- `./scripts/test-all.sh` passes with 0 failures in both environments
- No `pretty_midi`, `basic_pitch`, or `demucs` imported at module level
  (use `TYPE_CHECKING` guard)
- All new test files follow the existing naming and marker conventions
- All housekeeping tasks completed
- No regressions in existing tests

Do not start on the API (`src/api/`) — that stage has unresolved architecture
decisions and requires the project owner in the room.
