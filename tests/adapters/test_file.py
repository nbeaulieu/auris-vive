"""
Tests — src.adapters.file (FileAdapter)

FileAdapter is the only adapter that can be fully tested without mocking
network I/O or device access.  It is also the reference implementation of
the InputAdapter contract, so these tests double as a contract test spec
for all future adapters.
"""

from __future__ import annotations

import pytest

from src.adapters.base import AdapterError
from src.adapters.file import FileAdapter


# ── Happy path ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_returns_absolute_path(tmp_path):
    f = tmp_path / "track.flac"
    f.touch()
    async with FileAdapter(f) as adapter:
        path = await adapter.get_path()
    assert path.is_absolute()


@pytest.mark.asyncio
async def test_returns_correct_file(tmp_path):
    f = tmp_path / "track.flac"
    f.touch()
    async with FileAdapter(f) as adapter:
        path = await adapter.get_path()
    assert path.name == "track.flac"


@pytest.mark.asyncio
async def test_accepts_string_path(tmp_path):
    f = tmp_path / "track.wav"
    f.touch()
    async with FileAdapter(str(f)) as adapter:
        path = await adapter.get_path()
    assert path.exists()


@pytest.mark.asyncio
async def test_path_is_readable(tmp_path):
    f = tmp_path / "track.wav"
    f.write_bytes(b"\x00" * 64)
    async with FileAdapter(f) as adapter:
        path = await adapter.get_path()
    assert path.stat().st_size == 64


# ── Error cases ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_missing_file_raises_adapter_error(tmp_path):
    with pytest.raises(AdapterError):
        async with FileAdapter(tmp_path / "ghost.flac") as adapter:
            await adapter.get_path()


@pytest.mark.asyncio
async def test_directory_raises_adapter_error(tmp_path):
    with pytest.raises(AdapterError):
        async with FileAdapter(tmp_path) as adapter:
            await adapter.get_path()


@pytest.mark.asyncio
async def test_error_message_names_path(tmp_path):
    missing = tmp_path / "ghost.flac"
    with pytest.raises(AdapterError, match="ghost.flac"):
        async with FileAdapter(missing) as adapter:
            await adapter.get_path()


# ── Contract: AdapterError is the only exception type that escapes ─────────────

@pytest.mark.asyncio
async def test_no_raw_exceptions_escape(tmp_path):
    """
    Mirrors TC-ING-007's philosophy: domain exceptions only at the boundary.
    FileAdapter is simple enough that this is trivially true today, but the
    test locks in the expectation for when it grows (permissions, symlinks, etc.)
    """
    try:
        async with FileAdapter(tmp_path / "missing.wav") as adapter:
            await adapter.get_path()
    except AdapterError:
        pass
    except Exception as exc:
        pytest.fail(f"Raw exception escaped adapter boundary: {type(exc).__name__}: {exc}")


# ── Cleanup is a no-op (no resources to release) ──────────────────────────────

@pytest.mark.asyncio
async def test_cleanup_does_not_raise(tmp_path):
    f = tmp_path / "track.wav"
    f.touch()
    adapter = FileAdapter(f)
    await adapter.cleanup()  # should be silent
