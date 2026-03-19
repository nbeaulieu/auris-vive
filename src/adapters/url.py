"""
URL input adapter — SDD-007 (pending)

Downloads a remote audio file to a temp directory, yields the local path
to ingest, then cleans up on context exit.

Open questions
--------------
    Q-URL-1  Max download size — need a streaming limit before buffering to
             disk to avoid OOM on pathological inputs.
    Q-URL-2  Supported schemes — http/https only for now; s3:// is a likely
             future addition (direct boto3 download, skip HTTP layer).
    Q-URL-3  Auth headers — Apple Music / Spotify CDN URLs are pre-signed;
             no auth needed.  Internal asset URLs may need bearer tokens.
             Pass as constructor arg or read from env?
"""

from __future__ import annotations

from pathlib import Path

from src.adapters.base import AdapterError, InputAdapter


class URLAdapter(InputAdapter):
    def __init__(self, url: str) -> None:
        self._url = url
        self._tmp_dir: Path | None = None

    async def get_path(self) -> Path:
        raise NotImplementedError("SDD-007 pending — resolve Q-URL-1 first")

    async def cleanup(self) -> None:
        if self._tmp_dir and self._tmp_dir.exists():
            import shutil
            shutil.rmtree(self._tmp_dir, ignore_errors=True)
