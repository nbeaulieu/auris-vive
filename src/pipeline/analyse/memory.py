"""
MemoryCurvesSource — in-memory CurvesSource for testing and transient use.
"""

from __future__ import annotations

from src.pipeline.analyse.curves import StemCurves
from src.pipeline.analyse.source import CurvesSource


class MemoryCurvesSource(CurvesSource):
    """Simple dict-backed curves store. No persistence across process restarts."""

    def __init__(self) -> None:
        self._store: dict[str, StemCurves] = {}

    def save(self, stem_name: str, curves: StemCurves) -> None:
        self._store[stem_name] = curves

    def load(self, stem_name: str) -> StemCurves:
        if stem_name not in self._store:
            raise KeyError(f"no curves for stem '{stem_name}'")
        return self._store[stem_name]

    def exists(self, stem_name: str) -> bool:
        return stem_name in self._store

    def available_stems(self) -> list[str]:
        return list(self._store.keys())
