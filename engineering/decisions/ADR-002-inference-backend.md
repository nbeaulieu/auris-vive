# ADR-002 — Inference backend and job queue abstraction

| Field      | Value                                           |
|------------|-------------------------------------------------|
| Status     | Accepted                                        |
| Date       | 2026-03-19                                      |
| Deciders   | Architecture team                               |
| Relates to | ADR-001 (stack), SDD-003 (separate), SDD-006 (API + job queue) |

---

## 1. Context and problem statement

The Demucs source separation model requires a GPU to run at production-viable
latency (~25–40s on a T4 vs ~10 min on CPU for a 4-minute track). This creates
an infrastructure question: how and where does GPU inference run, and how does
the rest of the codebase stay insulated from that decision as it evolves?

Two sub-questions:

1. **Where does inference run?** What infrastructure hosts the GPU workload?
2. **How does the API submit work to it?** What abstraction sits between the
   API layer and the inference backend so the backend can change without
   touching application code?

---

## 2. Decision drivers

- **GPU is required in production** — Demucs inference on CPU is too slow for
  synchronous API responses. The infrastructure must provision GPU.
- **Scale to zero when idle** — Auris Vive is not a constant-traffic service.
  Paying for a resident GPU instance 24/7 during early development and low
  traffic periods is wasteful. The infrastructure should idle when no jobs are
  running.
- **Cold start must be manageable** — scale-to-zero means cold starts. Model
  weights (~80MB for htdemucs) must not be re-downloaded on every cold start.
  They should be cached on a persistent volume accessible to the inference
  container.
- **Local development must not require GPU or cloud credentials** — engineers
  should be able to run the full pipeline locally on CPU (slowly) without
  a Modal account, a GPU, or any cloud setup.
- **The API must not know how jobs are executed** — the inference backend is
  likely to change (from Modal to a different provider, or to a self-hosted
  fleet) as the product scales. The API layer must be insulated from this.

---

## 3. Considered options

### 3.1 Inference infrastructure

| Option | Notes |
|--------|-------|
| **Modal** ✓ | Selected — see below |
| AWS SageMaker | Enterprise ML serving. Significant ops overhead. Overkill for v1. |
| GCP Vertex AI | Similar to SageMaker. Same objections. |
| Fly.io persistent GPU VM | Persistent process, no scale-to-zero. Pay for idle GPU. |
| Self-hosted spot instances | Maximum control, maximum ops burden. Premature. |
| Replicate | Opinionated Cog packaging. Less control, faster to prototype. |

### 3.2 Job queue / abstraction pattern

| Option | Notes |
|--------|-------|
| **JobQueue ABC with pluggable backends** ✓ | Selected — see below |
| Direct Modal call from API route | Tight coupling. Changing backend requires changing API code. |
| Celery + Redis | Self-managed worker infrastructure. Unnecessary given Modal. |
| No abstraction (Modal everywhere) | Vendor lock-in baked into every layer. |

---

## 4. Decision

### 4.1 Modal as the v1 production inference backend

Modal is selected as the production inference backend for v1.

Modal is purpose-built for exactly Auris Vive's workload: bursty, GPU-dependent,
Python-native functions that should scale to zero when idle. The programming
model is a decorated Python function — the Demucs separation logic requires
minimal adaptation to run on Modal. Cold starts with weights on a Modal Volume
are ~2–3 seconds, acceptable for a queued job workflow.

Key Modal features used:

- `@modal.function(gpu="T4")` — GPU allocation per invocation
- `modal.Volume` — persistent volume for model weight caching; weights are
  downloaded once and reused across all subsequent cold starts
- Container keep-alive — Modal can hold a warm container between invocations
  to eliminate cold starts for sustained traffic periods
- Scale to zero — no charges when no jobs are running

### 4.2 Singleton model loading inside Modal containers

Two Demucs models are loaded as process-level singletons:

- **`htdemucs_ft`** — fine-tuned ensemble, authoritative for drums, bass,
  vocals, other. ~320MB (4-model ensemble).
- **`htdemucs_6s`** — 6-stem model, used exclusively for piano and guitar.
  ~80MB. Its versions of the 4 shared stems are discarded.

Both models run in parallel via `ThreadPoolExecutor`. PyTorch releases the GIL
during inference, so threading provides genuine parallelism on GPU. Total GPU
memory requirement is ~2.7GB — well within a T4's 16GB.

When Modal keeps a container warm between invocations, both models remain
loaded in GPU memory. Subsequent jobs pay only inference time (~25–40s per
model, running in parallel → ~25–40s wall time total).

```python
_models: dict[str, Model] = {}
_lock = threading.Lock()

def _get_model(name: str, device: torch.device) -> Model:
    if name not in _models:
        with _lock:
            if name not in _models:
                model = get_model(name)
                model.to(device)
                model.eval()
                _models[name] = model
    return _models[name]
```

### 4.3 Progressive stem delivery

The two models complete at approximately the same time (~25–40s each on T4).
An `on_stems_ready` callback allows the job runner to push partial results
to clients via WebSocket as each model completes, without waiting for both:

```
htdemucs_ft completes  → WebSocket: { "event": "stems_ready", "stems": ["drums", "bass", "vocals", "other"] }
htdemucs_6s completes  → WebSocket: { "event": "stems_ready", "stems": ["piano", "guitar"] }
                        → WebSocket: { "event": "job_complete" }
```

The visual layer begins rendering the core stems immediately, then overlays
piano and guitar when they arrive. The user sees visualisation start at
~25–40s rather than waiting for the full pipeline to complete.

### 4.4 JobQueue abstraction

A `JobQueue` ABC buffers the entire application from the inference backend.
The API layer calls `enqueue()` and `get_job()` — it never references Modal
directly.

```
src/api/job_queue/
    __init__.py        — JobQueue ABC, Job dataclass, JobStatus enum
    local.py           — LocalJobQueue: asyncio, runs pipeline in-process
    modal_backend.py   — ModalJobQueue: submits to Modal function
```

Backend is selected at startup via environment variable:

```python
JOB_QUEUE_BACKEND=local   # default — dev, CI, local testing
JOB_QUEUE_BACKEND=modal   # production
```

`LocalJobQueue` runs the pipeline synchronously in-process using an
`asyncio.Queue`. No Modal account, no GPU, no cloud credentials required.
CPU inference is slow but functional for development and the test suite.

`ModalJobQueue` submits jobs to the Modal function and polls for completion.
Modal handles all GPU provisioning, scaling, and container lifecycle.

### 4.4 Local backend emits a warning on CPU inference

When `LocalJobQueue` detects no GPU is available, it logs a warning:

```
WARNING  src.api.job_queue.local: no GPU detected — Demucs will run on CPU.
         Expect ~10 min for a 4-minute track. Set JOB_QUEUE_BACKEND=modal
         for production-speed inference.
```

This makes the performance implication explicit without blocking local use.

---

## 5. Architecture diagram

```
API layer (FastAPI)
  │
  │  enqueue(path) → Job
  │  get_job(id)   → Job
  ▼
JobQueue ABC
  ├── LocalJobQueue          (JOB_QUEUE_BACKEND=local)
  │     asyncio.Queue
  │     pipeline.runner.run()  ← in-process, CPU
  │
  └── ModalJobQueue          (JOB_QUEUE_BACKEND=modal)
        modal.Function.remote()
          └── Modal container (GPU T4)
                singleton model load from Volume
                pipeline.runner.run()
```

---

## 6. Consequences

### Positive

- The API layer has zero Modal imports. Swapping the backend is a one-line
  environment variable change.
- Local development requires no cloud setup. `pytest` and manual testing
  work immediately on any machine.
- Modal's scale-to-zero means no idle GPU cost during development and
  low-traffic periods.
- The singleton pattern inside Modal containers minimises per-job overhead
  when containers stay warm.
- Adding a third backend (e.g. self-hosted GPU fleet, AWS SageMaker) requires
  only a new class implementing `JobQueue` — no changes to the API layer.

### Negative / risks

- **Modal vendor dependency** — the production path depends on Modal's
  availability and pricing. Mitigated by the abstraction: migrating to a
  different backend is isolated to `modal_backend.py`.
- **Cold start latency** — even with cached weights, a cold start adds ~5–8s
  for two models. Acceptable for a queued job workflow; keep-alive strategy
  addresses sustained traffic.
- **Two-model GPU memory** — `htdemucs_ft` (~320MB) and `htdemucs_6s` (~80MB)
  plus buffers totals ~2.7GB on a T4. Well within budget but worth monitoring
  as the pipeline adds more stages.
- **Local inference is slow** — CPU inference (~10 min per model) is not
  viable for manual end-to-end testing locally. Use short clips (< 30s) or
  mock the separation stage in tests.

---

## 7. Future directions

- **Horizontal scaling** — multiple Modal workers, each with their own
  resident singleton, behind a job dispatcher. Modal handles this natively.
- **Spot / preemptible instances** — Modal supports spot GPU instances at
  lower cost. Viable once the pipeline is stable and job retry logic is in
  place.
- **On-device preview mode** — a lightweight model (smaller architecture,
  lower quality) converted to Core ML / TFLite for real-time visualisation
  on-device while the full pipeline processes server-side. Post-v1.
  See ADR-006 §5 (Option B future consideration).

---

## 8. Open questions

| ID | Question | Owner | Target |
|----|----------|-------|--------|
| Q-MODAL-1 | What is the keep-alive strategy for sustained traffic? Fixed TTL or demand-driven? | Infrastructure | SDD-006 |
| Q-MODAL-2 | Modal Volume vs EFS for model weight caching? Modal Volume is simpler; EFS relevant if we move off Modal. | Infrastructure | Pre-production |
| Q-GPU-1 | T4 sufficient for production latency SLA? A100 / H100 reduce inference to ~8–12s. Cost vs latency tradeoff. | Product | Pre-production |

---

## 9. References

- [Modal documentation](https://modal.com/docs)
- [Demucs — Meta Research](https://github.com/facebookresearch/demucs)
- ADR-001 — Technology stack (this repo)
- ADR-006 — Client integration strategy (this repo)
- SDD-003 — Separate stage (this repo, pending)
- SDD-006 — API and job queue (this repo, pending)
