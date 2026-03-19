# Project context — Auris Vive + Music Analysis Pipeline

This document provides context for all conversations in this project. Read it before responding to any query.

---

## Who I am

- 33 years in software engineering, currently a university professor
- Led teams of up to 105 people
- Building two products in parallel: **Auris Vive** (music intelligence platform) and **Zora Luxe** (real estate automation)
- Experienced enough that I don't need coaching — I need a sharp collaborator
- Prefer direct, technical, peer-level conversation. Skip the hand-holding.

---

## The product: Auris Vive

**Tagline:** *"The music was always this alive."*

**What it is:** A real-time music intelligence and visualisation platform. AI separates any audio stream into its constituent instruments, transcribes every note, and renders living generative visuals — simultaneously, in sync. Designed for embedding inside Apple Music and Spotify, as well as standalone.

**The three pillars:**
1. **Intelligence** — AI extraction (Demucs source separation + Basic Pitch transcription). Invisible to the user.
2. **Presence** — Real-time generative visuals that translate the music's structure into a living visual environment. Each stem has its own visual language.
3. **Stillness** — Focus, meditation, anxiety relief, sleep. The visual layer transforms music into an environment the nervous system can rest inside.

**Target audiences:** curious listeners, musicians studying recordings, people who need focus or calm.

**Portfolio context:** Auris Vive is developed alongside **Zora Luxe** (real estate automation). Both share the same design philosophy: AI does the extraction, design does the elevation.

---

## The name

- **Auris** — Latin for *ear*. The sonic intelligence underneath.
- **Vive** — French/Latin for *alive, living*. The visuals. The feeling.
- Together: *the living ear.* Or as a command: *hear it alive.*

---

## Brand identity

**Palette:**
| Name | Hex | Role |
|------|-----|------|
| Void | `#06060A` | Primary background |
| Dusk | `#1A1428` | Secondary background, cards |
| Deep | `#0E0B18` | Tertiary, subtle layering |
| Violet | `#7B5EA7` | AI-driven visuals, primary accent |
| Iris | `#A084C8` | Secondary visual accent |
| Gold | `#C9A96E` | Brand mark, active states |
| Pearl | `#E8E0D5` | Primary text on dark |
| Mist | `rgba(232,224,213,0.45)` | Secondary text, captions |

**Typography:**
- **Cormorant Garamond Light (300)** — display, brand voice, wordmark, track titles
- **Jost ExtraLight/Light (200–300)** — all UI copy, labels, metadata

**Voice:** Quiet confidence. Poetic precision. Never hype, never wellness clichés, never exclamation marks. "Play something." not "Play a song to get started!"

**Open design questions (D-01 through D-05):** What does each stem look like visually? How do visuals transition between stems? Does a calm mode exist? Is there a motion logo? Does Auris Vive have a light mode? (Current instinct: always dark.)

---

## Technical stack (ADR-001 — Accepted)

| Concern | Decision | Rationale |
|---------|----------|-----------|
| Language | Python | ML research ecosystem; Demucs and Basic Pitch have no equivalent elsewhere |
| Audio I/O | librosa | Decodes any format; returns NumPy array |
| Source separation | Demucs `htdemucs` | Hybrid waveform+spectrogram; best on MUSDB18 benchmark |
| Transcription | Basic Pitch (Spotify) | Handles polyphony; classical methods don't |
| MIDI representation | pretty_midi | Clean object model; native Basic Pitch output |
| Score generation | music21 | Understands music theory; MusicXML output |

---

## Pipeline architecture

```
Input adapter (file / URL / stream / device)
  ↓  path: str
Ingest          librosa decode → resample 44.1kHz → float32 [-1,1] → stereo (2,N)
  ↓  np.ndarray shape=(2,N) dtype=float32 sr=44100
Separate        Demucs htdemucs → { drums, bass, vocals, other }
  ↓  dict[str, np.ndarray]
Transcribe      Basic Pitch per stem → PrettyMIDI (drums → onset detection)
  ↓  dict[str, PrettyMIDI]
Outputs         FLAC stems / .mid files / MusicXML + PDF
  ↓  JobResult { stems, midi, score }
API             REST + WebSocket (FastAPI)
  ↓
Clients         Web embed JS SDK / Mobile SDK
```

**Key constraint:** Demucs is too slow on CPU (~10 min for a 4-min track). GPU required in production (~25–40s on T4).

---

## Document inventory

| Doc | Status | Location |
|-----|--------|----------|
| ADR-001 — Technology stack | ✅ Written | `engineering/decisions/ADR-001-stack.md` |
| ADR-006 — Client integration strategy | ✅ Written | `engineering/decisions/ADR-006-client-integration.md` |
| SDD-001 — Pipeline overview | 🔄 In progress | `engineering/design/SDD-001-pipeline-overview.html` |
| SDD-002 — Ingest stage | ✅ Written | `engineering/design/SDD-002-ingest-stage.md` |
| SDD-003 — Separate (Demucs) | 🔲 Pending | — |
| SDD-004 — Transcribe (Basic Pitch) | ✅ Written | `engineering/design/SDD-004-transcribe-stage.md` |
| SDD-005 — Outputs (FLAC + MIDI) | ✅ Written | `engineering/design/SDD-005-outputs-stage.md` |
| SDD-006 — API + job queue | 🔲 Pending | — |
| SDD-007 — Input adapters | 🔲 Pending | — |
| ADR-002 — Inference backend | ✅ Written | `engineering/decisions/ADR-002-inference-backend.md` |
| ADR-003 — Drum stem handling | ✅ Written | `engineering/decisions/ADR-003-drum-transcription.md` |
| ADR-004 — Score quantisation | 🔲 Pending | — |
| ADR-005 — Multi-channel downmix | 🔲 Pending | — |

---

## Repo structure

```
auris-vive/
├── README.md               Product front door
├── .github/
│   └── CONTRIBUTING.md     How to add ADRs, SDDs, brand files
├── brand/
│   ├── README.md           Design entry point + open design questions
│   ├── VISION.md           Three pillars, philosophy, what it isn't
│   ├── identity.html       Living brand sketch (open in browser)
│   ├── palette.md          Colour system
│   ├── typography.md       Type system
│   └── voice.md            Brand voice guide with right/wrong examples
├── engineering/
│   ├── README.md           Technical entry point + document map
│   ├── PROJECT-CONTEXT.md  Project context and conversation conventions
│   ├── decisions/          ADRs
│   └── design/             SDDs
└── src/
    ├── README.md           Code directory guide
    ├── pipeline/           ingest, separate, transcribe, outputs, runner
    ├── api/                FastAPI server, routes, job queue, WebSocket
    │   └── routes/
    ├── adapters/           file, URL, stream, device
    └── clients/
        ├── web/            JS SDK
        └── mobile/         iOS + Android stubs
```

Monorepo for now. Split when team size justifies it.

---

## Key open questions (18 total — see SDD-001 for full registry)

Most blocking:

| ID | Question | Blocks |
|----|----------|--------|
| Q-STREAM-1 | Batch vs rolling-window streaming | Stream adapter, pipeline design |
| Q-TRX-2 | Drum transcription — ADTLib vs onset-only vs skip | SDD-004, ADR-003 |
| Q-SEP-1 | Model loading — singleton vs per-job | SDD-003, ADR-002 |
| Q-API-1 | Authentication model | SDD-006 |

---

## Conversation conventions

- **Tone:** peer-level, direct, technical. No over-explaining. No bullet-point padding.
- **Docs follow arc42 structure** — ADRs for decisions, SDDs for stage design
- **Next logical build target:** `src/pipeline/ingest.py` — fully specced in SDD-002, ready to write
- **Brand collaborator:** artist partner involved in visual identity — keep brand language accessible to non-engineers
- **Document numbering:** ADR-00X for decisions, SDD-00X for design docs, sequential
- **Client integration is decided (ADR-006):** all clients are thin API wrappers — no ML on-device, no embedded Python. The pipeline is server-side only. Don't re-open this unless discussing the post-v1 on-device preview mode.
