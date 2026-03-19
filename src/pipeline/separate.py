"""
Separate stage — SDD-003 (pending)

Consumes the normalised stereo array from ingest and returns per-stem waveforms
via Demucs htdemucs.

Contract
--------
    input  : audio: np.ndarray  shape=(2, N)  dtype=float32  sr=44100
    output : dict[str, np.ndarray]
               keys    : "drums" | "bass" | "vocals" | "other"
               values  : np.ndarray  shape=(2, N)  dtype=float32  sr=44100

Open questions (see SDD-003)
----------------------------
    Q-SEP-1  Model loading strategy — singleton vs per-job.
             Singleton keeps the model resident in GPU memory between jobs
             (preferred for throughput); per-job is simpler but adds ~3s
             cold-start on T4.  Decision deferred to ADR-002.
"""

from __future__ import annotations

import numpy as np


class SeparateError(Exception):
    """Domain exception for the separate stage."""


STEM_NAMES: tuple[str, ...] = ("drums", "bass", "vocals", "other")


def separate(audio: np.ndarray) -> dict[str, np.ndarray]:
    """
    Run Demucs htdemucs source separation.

    Parameters
    ----------
    audio : np.ndarray
        Normalised stereo array from ingest.
        shape=(2, N), dtype=float32, sr=44100.

    Returns
    -------
    dict[str, np.ndarray]
        One entry per stem.  Each array shares the shape and dtype of the
        input.  Sample count N may differ by ≤ 1 sample due to Demucs
        internal padding; downstream stages must tolerate this.

    Raises
    ------
    SeparateError
        Any failure from model load through stem extraction.
    """
    raise NotImplementedError("SDD-003 pending — see Q-SEP-1 before implementing")
