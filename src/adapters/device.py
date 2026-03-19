"""
Device input adapter — SDD-007 (pending)

Captures audio from a local input device (microphone, line-in) into a temp
file for ingest.  Primarily useful for live instrument analysis.

Likely implementation: sounddevice → write to temp WAV → return path.
Cross-platform device enumeration is non-trivial; punt until there's
a concrete use case driving the requirement.
"""

from __future__ import annotations

from pathlib import Path

from src.adapters.base import InputAdapter


class DeviceAdapter(InputAdapter):
    async def get_path(self) -> Path:
        raise NotImplementedError("SDD-007 pending — no concrete use case yet")
