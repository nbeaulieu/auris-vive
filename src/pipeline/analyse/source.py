"""
CurvesSource ABC — persistence interface for StemCurves.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.pipeline.analyse.curves import StemCurves


class CurvesSource(ABC):
    """Abstract base class for loading and saving StemCurves."""

    @abstractmethod
    def save(self, stem_name: str, curves: StemCurves) -> None:
        """Persist curves for a single stem."""

    @abstractmethod
    def load(self, stem_name: str) -> StemCurves:
        """Load previously saved curves for a stem."""

    @abstractmethod
    def exists(self, stem_name: str) -> bool:
        """Return True if curves exist for the given stem."""

    @abstractmethod
    def available_stems(self) -> list[str]:
        """Return names of all stems with saved curves."""
