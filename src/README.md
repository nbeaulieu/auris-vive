# Source

This directory contains all Auris Vive application code. For architecture decisions and stage design documents, see [`../engineering/`](../engineering/). For brand and visual identity, see [`../brand/`](../brand/).

---

## Structure

```
src/
├── pipeline/       Core audio processing — ingest, separate, transcribe, output
├── api/            REST + WebSocket server — job management, file serving
├── adapters/       Input adapters — file, URL, stream, device
└── clients/        Web embed SDK and mobile SDK wrappers
```

---

## `pipeline/`

The heart of the system. Four sequential stages that transform an audio file into stems, MIDI, and a score. Each stage is a pure function — it receives a typed input, performs computation, and returns a typed output. No stage writes to disk; the pipeline runner handles all persistence.

```
pipeline/
├── runner.py       PipelineRunner — orchestrates all four stages, emits progress events
├── ingest.py       Stage 1 — decode, resample to 44.1kHz, normalise to float32 stereo
├── separate.py     Stage 2 — Demucs htdemucs source separation → 4 stems
├── transcribe.py   Stage 3 — Basic Pitch per-stem transcription → PrettyMIDI
├── outputs.py      Stage 4 — serialise stems to FLAC, MIDI to .mid, score to MusicXML/PDF
└── errors.py       Shared exception types — IngestError, SeparationError, etc.
```

Design specification: [`../engineering/design/`](../engineering/design/)
Stage contracts: [`../engineering/design/SDD-001-pipeline-overview.html`](../engineering/design/SDD-001-pipeline-overview.html)

---

## `api/`

The REST and WebSocket server. Accepts job submissions, queues them for processing, tracks status, and serves completed artifacts. Does not perform any audio processing — it calls into `pipeline/` via the job queue.

```
api/
├── main.py         Application entry point and server config
├── routes/
│   ├── jobs.py     POST /jobs, GET /jobs/:id, DELETE /jobs/:id
│   └── outputs.py  GET /jobs/:id/outputs and file streaming endpoints
├── queue.py        Job queue — submits pipeline runs, tracks state
├── ws.py           WebSocket progress channel — broadcasts stage events to clients
└── models.py       Pydantic models — JobRequest, JobResult, JobStatus
```

API spec: [`../engineering/design/SDD-006-api.md`](../engineering/design/SDD-006-api.md) *(pending)*

---

## `adapters/`

Input adapters. Each adapter has one job: accept a source-specific input and return a path to a local audio file. The pipeline never knows or cares which adapter was used.

```
adapters/
├── base.py         AdapterBase — the shared interface all adapters implement
├── file.py         File adapter — validates local path and supported format
├── url.py          URL adapter — yt-dlp for YouTube/SoundCloud, httpx for direct URLs
├── stream.py       Stream adapter — buffers WebSocket audio to a temp file
└── device.py       Device adapter — reserved; likely handled client-side (see below)
```

Adapter design: [`../engineering/design/SDD-007-adapters.md`](../engineering/design/SDD-007-adapters.md) *(pending)*

---

## `clients/`

Client-facing SDKs. These are thin wrappers over the REST and WebSocket API — they contain no audio processing logic. All heavy computation happens server-side in `pipeline/`.

```
clients/
├── web/            JavaScript SDK — npm package for web embed and browser integration
└── mobile/         Mobile SDK stubs — iOS (Swift) and Android (Kotlin) *(TBD)*
```

Client design questions: see open questions Q-WEB-1, Q-MOB-1 in [`../engineering/design/SDD-001-pipeline-overview.html`](../engineering/design/SDD-001-pipeline-overview.html)

---

## Dependencies

Full dependency list will live in `requirements.txt` (Python) and `package.json` (JS clients). Core runtime dependencies:

| Package | Used in | Purpose |
|---------|---------|---------|
| `librosa` | `pipeline/ingest.py` | Audio decode and normalisation |
| `demucs` | `pipeline/separate.py` | Neural source separation |
| `basic-pitch` | `pipeline/transcribe.py` | Polyphonic transcription |
| `pretty_midi` | `pipeline/transcribe.py` | MIDI object model |
| `music21` | `pipeline/outputs.py` | Score generation and MusicXML |
| `soundfile` | `pipeline/outputs.py` | FLAC stem serialisation |
| `fastapi` | `api/` | REST + WebSocket server |
| `yt-dlp` | `adapters/url.py` | YouTube / SoundCloud extraction |

---

## Environment

```bash
# Python 3.11+
pip install -r requirements.txt

# FFmpeg required for MP3/MP4 decoding
brew install ffmpeg        # macOS
apt install ffmpeg         # Ubuntu / Debian

# GPU strongly recommended for Demucs
# CPU inference is ~10 min per 4-min track
# See ADR-002 for GPU provisioning strategy (pending)
```

---

*Code questions → open an issue tagged `engineering`*
*Pipeline design questions → see [`../engineering/`](../engineering/) before opening an issue*
