"""
DiskCurvesSource — file-backed CurvesSource.

Files are stored under a base directory with the naming convention:
    <stem>_<curve>.npy   — one per curve
    <stem>_meta.json     — fps and sr
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np

from src.pipeline.analyse.curves import CURVE_NAMES, AnalyseError, StemCurves
from src.pipeline.analyse.source import CurvesSource

logger = logging.getLogger(__name__)


class DiskCurvesSource(CurvesSource):
    """
    Persist StemCurves as .npy files + JSON metadata on disk.

    Parameters
    ----------
    base_dir : Path | str
        Directory where curve files are written.  Created on first save().
    """

    def __init__(self, base_dir: Path | str) -> None:
        self._base = Path(base_dir)

    def save(self, stem_name: str, curves: StemCurves) -> None:
        """
        Write all six curves as .npy and metadata as JSON.

        Creates the directory if it doesn't exist.
        """
        self._base.mkdir(parents=True, exist_ok=True)

        for name, arr in curves.curve_dict().items():
            np.save(str(self._base / f"{stem_name}_{name}.npy"), arr)

        meta = {"fps": curves.fps, "sr": curves.sr}
        meta_path = self._base / f"{stem_name}_meta.json"
        meta_path.write_text(json.dumps(meta))

        logger.debug("saved curves for '%s' to %s", stem_name, self._base)

    def load(self, stem_name: str) -> StemCurves:
        """
        Load curves from disk.

        Raises
        ------
        AnalyseError
            If any expected file is missing or unreadable.
        """
        meta_path = self._base / f"{stem_name}_meta.json"
        if not meta_path.exists():
            raise AnalyseError(f"metadata not found: {meta_path}")

        try:
            meta = json.loads(meta_path.read_text())
        except Exception as exc:
            raise AnalyseError(f"failed to read metadata: {meta_path}: {exc}") from exc

        arrays: dict[str, np.ndarray] = {}
        for name in CURVE_NAMES:
            npy_path = self._base / f"{stem_name}_{name}.npy"
            if not npy_path.exists():
                raise AnalyseError(f"curve file not found: {npy_path}")
            arrays[name] = np.load(str(npy_path)).astype(np.float32)

        return StemCurves(
            **arrays,
            fps=int(meta["fps"]),
            sr=int(meta["sr"]),
        )

    def exists(self, stem_name: str) -> bool:
        meta_path = self._base / f"{stem_name}_meta.json"
        return meta_path.exists()

    def available_stems(self) -> list[str]:
        if not self._base.exists():
            return []
        # Discover stems by finding *_meta.json files
        stems = []
        for p in sorted(self._base.glob("*_meta.json")):
            stem_name = p.name.removesuffix("_meta.json")
            stems.append(stem_name)
        return stems
