"""
src.pipeline.analyse — per-stem visualisation curve extraction.

Sits after the separate stage.  Extracts six normalised time-series curves
per stem that the visual layer drives animations from.

    from src.pipeline.analyse.analyse import analyse
    from src.pipeline.analyse.curves import StemCurves, AnalyseError
    from src.pipeline.analyse.source import CurvesSource
    from src.pipeline.analyse.disk import DiskCurvesSource
    from src.pipeline.analyse.memory import MemoryCurvesSource
"""

from src.pipeline.analyse.analyse import analyse
from src.pipeline.analyse.curves import AnalyseError, StemCurves
from src.pipeline.analyse.disk import DiskCurvesSource
from src.pipeline.analyse.memory import MemoryCurvesSource
from src.pipeline.analyse.source import CurvesSource

__all__ = [
    "analyse",
    "AnalyseError",
    "StemCurves",
    "CurvesSource",
    "DiskCurvesSource",
    "MemoryCurvesSource",
]
