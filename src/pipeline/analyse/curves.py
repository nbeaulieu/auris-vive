"""
StemCurves dataclass and AnalyseError — analyse stage data types.

Each StemCurves holds seven normalised time-series curves extracted from a single
separated stem.  All curves are float32, shape (T,), values in [0.0, 1.0].
The visual layer drives animations directly from these arrays.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


class AnalyseError(Exception):
    """Domain exception for the analyse stage."""


CURVE_NAMES: tuple[str, ...] = (
    "energy",
    "brightness",
    "onset",
    "warmth",
    "texture",
    "flux",
    "pitch_curve",
)


@dataclass
class StemCurves:
    """
    Seven normalised visualisation curves for a single stem.

    Attributes
    ----------
    energy      : RMS power envelope
    brightness  : spectral centroid (normalised to [0, 1])
    onset       : onset strength
    warmth      : low-frequency energy ratio (< 300 Hz)
    texture     : spectral flatness (0 = tonal, 1 = noisy)
    flux        : spectral flux (frame-to-frame change)
    pitch_curve : fundamental frequency (0 = unvoiced, >0 = pitched)
    fps         : frames per second these were computed at
    sr          : sample rate of the source audio
    """

    energy: np.ndarray
    brightness: np.ndarray
    onset: np.ndarray
    warmth: np.ndarray
    texture: np.ndarray
    flux: np.ndarray
    pitch_curve: np.ndarray
    fps: int
    sr: int

    def at_fps(self, target_fps: int) -> StemCurves:
        """
        Decimate to a lower frame rate via stride slicing.

        Parameters
        ----------
        target_fps : int
            Desired output frame rate.  Must be <= self.fps.
            Upsampling is out of scope (Q-ANA-2).

        Returns
        -------
        StemCurves
            New instance at the target frame rate.
        """
        if target_fps >= self.fps:
            return self
        stride = self.fps // target_fps
        return StemCurves(
            energy=self.energy[::stride],
            brightness=self.brightness[::stride],
            onset=self.onset[::stride],
            warmth=self.warmth[::stride],
            texture=self.texture[::stride],
            flux=self.flux[::stride],
            pitch_curve=self.pitch_curve[::stride],
            fps=target_fps,
            sr=self.sr,
        )

    def curve_dict(self) -> dict[str, np.ndarray]:
        """Return all seven curves as a name → array dict."""
        return {
            "energy": self.energy,
            "brightness": self.brightness,
            "onset": self.onset,
            "warmth": self.warmth,
            "texture": self.texture,
            "flux": self.flux,
            "pitch_curve": self.pitch_curve,
        }
