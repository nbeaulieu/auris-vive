"""
Input adapter base class — SDD-007 (pending)

All adapters share one contract: produce a path that ingest can consume.
Each adapter is responsible for its own resource management (temp files,
HTTP sessions, device handles).  Ingest never sees those details.

Adapters are async because URL downloads and device capture are inherently
I/O-bound.  File adapters are trivially async (they just return the path).
"""

from __future__ import annotations

import abc
from pathlib import Path


class AdapterError(Exception):
    """Domain exception for all input adapters."""


class InputAdapter(abc.ABC):
    """
    Abstract base for all input adapters.

    Usage pattern
    -------------
        async with FileAdapter("/path/to/track.flac") as adapter:
            path = await adapter.get_path()
            audio = load(path)

    The context manager handles any setup/teardown (temp dir cleanup for URL
    downloads, device stream teardown, etc.).  Callers must not hold the path
    after exiting the context — it may no longer be valid.
    """

    @abc.abstractmethod
    async def get_path(self) -> Path:
        """
        Resolve or produce a readable local file path.

        Returns
        -------
        Path
            Absolute path to a readable audio file.

        Raises
        ------
        AdapterError
            Any failure specific to this adapter's source type.
        """

    async def __aenter__(self) -> "InputAdapter":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.cleanup()

    async def cleanup(self) -> None:
        """Override to release resources (temp files, network sessions, etc.)."""
