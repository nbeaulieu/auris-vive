"""
Stream input adapter — SDD-007 (pending)

Accepts a rolling audio stream (e.g. live broadcast, real-time device feed)
and produces a buffered path for ingest.

The core architectural question here is Q-STREAM-1: do we buffer a fixed
window (batch mode, simpler) or process overlapping rolling windows and stitch
stems (lower latency, significantly more complex)?  This adapter's design
is entirely driven by that decision.  Do not implement until ADR is accepted.

Open questions
--------------
    Q-STREAM-1  Batch vs rolling-window streaming.
                Blocks: stream adapter design, pipeline runner threading model.
"""

from __future__ import annotations

from pathlib import Path

from src.adapters.base import InputAdapter


class StreamAdapter(InputAdapter):
    async def get_path(self) -> Path:
        raise NotImplementedError("SDD-007 pending — blocked on Q-STREAM-1 / ADR decision")
