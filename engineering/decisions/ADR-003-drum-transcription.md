# ADR-003 — Drum stem transcription approach

| Field      | Value                                              |
|------------|----------------------------------------------------|
| Status     | Accepted                                           |
| Date       | 2026-03-19                                         |
| Deciders   | Architecture team                                  |
| Relates to | ADR-001 (stack), SDD-003 (separate), SDD-004 (transcribe) |

---

## 1. Context and problem statement

The transcribe stage runs Basic Pitch on each separated stem to produce MIDI.
Basic Pitch is a pitch estimator — it works well on pitched instruments (bass,
vocals, piano, guitar) but produces meaningless output on the drum stem, which
contains unpitched percussive transients rather than sustained pitched notes.

A dedicated strategy is required for the drum stem that produces useful output
within the same `dict[str, PrettyMIDI]` contract the transcribe stage defines,
without routing drums through Basic Pitch.

---

## 2. Why Basic Pitch fails on drums

Basic Pitch uses a neural network trained to detect fundamental frequencies
in audio. A snare hit, kick drum, or cymbal has no stable fundamental
frequency — it is a broadband transient. The model either produces no output
(silent passages between hits register as silence correctly) or hallucinates
pitches in the noise floor. The resulting MIDI is not useful for either
visualisation or score generation.

---

## 3. Considered options

### Option A — Skip drum transcription (return empty PrettyMIDI)

Return an empty `PrettyMIDI` object for the drum stem. Honest about the
limitation. No spurious MIDI output.

**Rejected because:** the visual layer needs rhythmic pulse information from
the drum stem. Empty MIDI means the visuals have no beat grid, no transient
triggers, no temporal structure from the most rhythmically important stem.
This is a significant gap for the Presence pillar.

### Option B — Onset detection only (selected for v1)

Use `librosa.onset.onset_detect()` to find the timestamps of percussive
transients in the drum stem. Map each onset to a generic MIDI note
(snare = GM 38) at a fixed velocity. The result is a rhythmically accurate
MIDI track that encodes *when* hits occur, without distinguishing *which*
drum instrument produced them.

No additional ML model. No additional dependency. Runs on CPU in milliseconds.
Slots directly into the `PrettyMIDI` output contract.

**Selected for v1.**

### Option C — ADTLib (Automatic Drum Transcription)

A dedicated drum transcription model that classifies individual drum
instruments (kick, snare, hi-hat, ride, crash, toms) and maps them to
standard GM MIDI note numbers. Produces genuine, musically useful drum MIDI.

**Rejected for v1 because:**
- Adds a heavy ML dependency and a second model to the inference pipeline
- Increases cold start time and GPU memory footprint
- Drum transcription quality is variable and less mature than Demucs or
  Basic Pitch — requires evaluation before committing
- The product does not yet require per-instrument drum MIDI (visualisation
  of kick vs hi-hat is a post-v1 feature)

**Targeted for v2.** The `DrumTranscriber` abstraction (see §4) is designed
to make this swap straightforward.

---

## 4. Decision

### 4.1 Onset-only transcription for v1

For v1, drum stems are transcribed using onset detection:

```python
import librosa
import pretty_midi

def transcribe_drums(stem: np.ndarray, sr: int = 44100) -> pretty_midi.PrettyMIDI:
    # Detect onset times in the drum stem
    onset_frames = librosa.onset.onset_detect(y=stem[0], sr=sr, units="time")

    midi = pretty_midi.PrettyMIDI()
    drums = pretty_midi.Instrument(program=0, is_drum=True, name="Drums")

    for onset_time in onset_frames:
        note = pretty_midi.Note(
            velocity=100,
            pitch=38,           # GM snare — generic placeholder
            start=onset_time,
            end=onset_time + 0.05,
        )
        drums.notes.append(note)

    midi.instruments.append(drums)
    return midi
```

The output is a valid `PrettyMIDI` object with a drum instrument track.
Downstream stages (outputs, visual layer) receive it identically to any
other stem's MIDI. The generic pitch (GM 38) is a known limitation,
documented in the job result metadata.

### 4.2 DrumTranscriber abstraction

To isolate the transcribe stage from the drum strategy and make the v2
upgrade to ADTLib a drop-in replacement, drum transcription is encapsulated
behind a `DrumTranscriber` ABC:

```
src/pipeline/drums/
    __init__.py          — DrumTranscriber ABC
    onset.py             — OnsetTranscriber (v1)
    adtlib.py            — ADTLibTranscriber (v2 stub)
```

The `DrumTranscriber` interface:

```python
class DrumTranscriber(abc.ABC):
    @abc.abstractmethod
    def transcribe(self, stem: np.ndarray, sr: int = 44100) -> pretty_midi.PrettyMIDI:
        """Transcribe a drum stem to MIDI."""
```

The transcribe stage receives a `DrumTranscriber` instance and calls
`transcribe()` — it never references `OnsetTranscriber` or `ADTLibTranscriber`
directly. The active implementation is selected via configuration.

### 4.3 Visual layer contract

The `PrettyMIDI` output from onset detection encodes rhythmic pulse as note
onset times. The visual layer uses these timestamps as transient triggers —
it does not need to know which drum instrument produced the hit for v1.

When ADTLib lands in v2, GM note numbers will distinguish instruments:

| GM note | Instrument |
|---------|------------|
| 36 | Kick drum |
| 38 | Snare |
| 42 | Closed hi-hat |
| 46 | Open hi-hat |
| 49 | Crash cymbal |
| 51 | Ride cymbal |

The visual layer should be written to inspect note numbers and apply
per-instrument visual treatment where available, falling back to generic
transient behaviour when all notes are GM 38 (v1 output). This way the
visual upgrade happens automatically when ADTLib ships.

---

## 5. Consequences

### Positive

- No new ML dependency. Onset detection runs on CPU with librosa, which is
  already in the stack.
- Rhythmic pulse is available to the visual layer from day one.
- The `DrumTranscriber` abstraction means the upgrade path to ADTLib is
  a new class, not a refactor.
- The visual layer can be written to take advantage of per-instrument MIDI
  in v2 without any structural changes.

### Negative / risks

- **Generic pitch** — all drum hits map to GM 38. Score output for the drum
  stem is not musically meaningful in v1. This should be communicated clearly
  in the job result metadata.
- **No instrument differentiation** — kick, snare, and cymbal are
  indistinguishable in the v1 output. The visual layer cannot render
  per-instrument treatments until v2.
- **Onset sensitivity** — `librosa.onset.onset_detect()` has tunable
  parameters (delta, wait, pre/post max). Default values work well on most
  material but may over-detect on dense passages or under-detect on sparse
  ones. May need per-genre tuning. Tracked as Q-DRUM-1.

---

## 6. Open questions

| ID | Question | Owner | Target |
|----|----------|-------|--------|
| Q-DRUM-1 | What onset detection parameters work best across genres? Default librosa values vs tuned per-genre? | ML | Evaluation sprint |
| Q-DRUM-2 | When is ADTLib ready to evaluate? What quality threshold justifies the added dependency? | ML | Post-v1 |
| Q-DRUM-3 | Should onset velocity be derived from the onset strength envelope rather than fixed at 100? More expressive output for the visual layer. | ML | SDD-004 |

---

## 7. References

- [librosa onset detection](https://librosa.org/doc/latest/onset.html)
- [ADTLib](https://github.com/CarlSouthall/ADTLib) — Automatic Drum Transcription
- [General MIDI drum note map](https://en.wikipedia.org/wiki/General_MIDI#Percussion)
- ADR-001 — Technology stack (this repo)
- SDD-004 — Transcribe stage (this repo, pending)
