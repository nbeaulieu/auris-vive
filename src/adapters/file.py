"""
File input adapter

Simplest adapter: validates a local path and returns it unchanged.
No I/O, no temp files — cleanup is a no-op.

This is the reference implementation for the adapter contract.
"""

from __future__ import annotations

from pathlib import Path

from src.adapters.base import AdapterError, InputAdapter


class FileAdapter(InputAdapter):
    """
    Adapter for local filesystem paths.

        async with FileAdapter("/absolute/path/track.flac") as adapter:
            path = await adapter.get_path()
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    async def get_path(self) -> Path:
        if not self._path.exists():
            raise AdapterError(f"file not found: {self._path}")
        if not self._path.is_file():
            raise AdapterError(f"path is not a file: {self._path}")
        return self._path.resolve()
