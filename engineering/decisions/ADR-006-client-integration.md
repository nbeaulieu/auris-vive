# ADR-006 — Client integration strategy

| Field      | Value                                      |
|------------|--------------------------------------------|
| Status     | Accepted                                   |
| Date       | 2026-03-19                                 |
| Deciders   | Architecture team                          |
| Relates to | SDD-001 (pipeline overview), SDD-006 (API) |

---

## 1. Context and problem statement

Auris Vive's core pipeline is written in Python and depends on Demucs (neural source separation) and Basic Pitch (polyphonic transcription). The product must deliver experiences on at least three client surfaces: iOS, Android, and web (including embedded contexts inside Apple Music and Spotify).

The question is how Python and the ML pipeline relate to those client surfaces. There are four meaningful options. This ADR documents all of them, explains why three were rejected for v1, and establishes the accepted approach.

---

## 2. Considered options

### Option A — API server (accepted)

Python runs as a backend service on GPU-provisioned infrastructure. All clients communicate with it over REST and WebSocket. Clients are thin wrappers — they submit audio, subscribe to a progress channel, and download results. They contain no ML logic and no Python.

### Option B — On-device inference

ML models are converted from PyTorch to a mobile-native format (Core ML for Apple, TFLite or ONNX for cross-platform) and shipped inside the app bundle. Processing happens locally on the device.

### Option C — Embedded Python runtime

Python is bundled directly into the native app using tools like BeeWare/Briefcase, PyObjC, or Python for Unity. The full pipeline runs inside the app process.

### Option D — WebAssembly

Python or the ML models are compiled to WASM and run in the browser. Relevant only for the web embed client.

---

## 3. Decision drivers

- **GPU dependency** — Demucs inference takes ~10 minutes on a modern CPU for a 4-minute track. It requires a GPU for production-viable latency (~25–40s on a T4). GPUs live in data centres, not phones.
- **Model weight size** — `htdemucs` model weights are ~80MB. Shipping this in an app bundle is impractical and would likely trigger App Store review concerns.
- **Client surface diversity** — the same pipeline must serve iOS, Android, web embeds, and Spotify/Apple Music integrations. A server-side API is the only approach that serves all surfaces from a single implementation.
- **Separation of concerns** — clients should not know or care how the pipeline works. The API is the contract. This makes client implementations simple and lets the pipeline evolve independently.
- **Operational simplicity** — one server, one codebase, one deployment. Scaling is additive: more GPU workers behind a load balancer.

---

## 4. Decision

**Option A — API server — is accepted for v1 and the foreseeable future.**

Python runs server-side. All clients speak REST + WebSocket. No ML logic runs on client devices.

The mental model for client developers: this is exactly the pattern used in game backend services. A Unity game does not run matchmaking or leaderboard logic on-device — it calls an API. Auris Vive clients should think about the pipeline the same way. The Python pipeline is the backend service. The mobile app or web embed is the client. The API is the contract.

---

## 5. Option-by-option rejection rationale

### Option B — On-device inference — rejected for v1

**Why rejected:**
- Demucs has not been reliably converted to Core ML or TFLite. The hybrid waveform+spectrogram architecture makes conversion non-trivial.
- Even if conversion succeeded, a 4-minute track would take significantly longer than 40s on mobile silicon — the same CPU bottleneck that makes server-side GPU necessary.
- App bundle size with model weights would exceed 500MB.

**Future consideration:** a lightweight on-device model — smaller, lower quality, faster — could serve as a "preview mode" for real-time visualisation while the full server-side pipeline processes in the background. This is a v2+ consideration. Basic Pitch is a stronger candidate for on-device conversion than Demucs; Spotify has done exploratory work in this direction.

### Option C — Embedded Python runtime — rejected

**Why rejected:**
- Embedding Python does not embed a GPU. The fundamental performance constraint remains.
- App bundle size balloons: Python runtime + PyTorch + model weights exceeds 500MB.
- App Store review of apps with interpreted runtimes is more complex and less predictable.
- Tools like BeeWare and PyObjC work well for simple Python apps; they are not designed for GPU-accelerated ML inference pipelines.

### Option D — WebAssembly — partially relevant, deferred

**Why deferred rather than rejected:**
- WASM cannot run Demucs at viable speed — the GPU dependency applies here too.
- However, WASM is a credible future option for lightweight client-side audio analysis: waveform display, onset detection, basic frequency analysis. Running these in the browser client-side would reduce server load for the visualisation layer without requiring full pipeline execution.
- This is a web embed optimisation, not a pipeline replacement. Deferred to post-v1.

---

## 6. Architecture consequence

All client surfaces — iOS, Android, web embed, Spotify integration, Apple Music integration — are thin API clients. They share the same interface and the same mental model:

```
Client (any platform)
  POST /jobs          — submit audio (file upload or URL)
  GET  /jobs/:id      — poll status
  WSS  /jobs/:id/progress — subscribe to real-time stage events
  GET  /jobs/:id/outputs/:type/:stem — download artifacts
```

A client implementation is a few hundred lines in any language. The complexity lives in the pipeline, not the client.

---

## 7. Implications for the mobile SDK

The mobile SDK (SDD-007, pending) must handle one pattern that differs from a standard REST client: artifact download. Results include binary file downloads — FLAC stems, MIDI files, MusicXML — not just JSON responses. The SDK must handle chunked binary downloads gracefully and provide progress reporting for large file transfers.

---

## 8. Implications for the web embed

The web embed SDK is a JavaScript package that wraps the API. For device capture (microphone → pipeline), the browser handles `MediaRecorder` audio capture and the SDK uploads the resulting blob as a file. The server-side adapter receives it as a standard file upload. No special server-side handling is required for device-sourced audio.

---

## 9. Open questions

| ID | Question | Owner | Target |
|----|----------|-------|--------|
| Q-ONDEV-1 | When is on-device inference viable? What model size / quality tradeoff is acceptable for a "preview mode"? | ML | Post-v1 |
| Q-WASM-1 | Which lightweight audio analysis operations are worth moving to WASM in the web embed? | Engineering | Post-v1 |

---

## 10. References

- [Core ML Tools — PyTorch conversion](https://coremltools.readme.io/docs/pytorch-conversion)
- [Basic Pitch — Spotify Research](https://github.com/spotify/basic-pitch)
- [Demucs — Meta Research](https://github.com/facebookresearch/demucs)
- [BeeWare — Python on mobile](https://beeware.org)
- SDD-001 — Pipeline overview (this repo)
- SDD-006 — API and job queue (this repo, pending)
