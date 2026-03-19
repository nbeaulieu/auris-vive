"""
src.adapters — input adapters

All adapters implement InputAdapter and are used as async context managers:

    async with FileAdapter("/path/to/track.flac") as adapter:
        path = await adapter.get_path()
        audio = load(path)

Adding a new adapter: subclass InputAdapter, implement get_path(),
override cleanup() if you allocate resources.  Zero changes to ingest
or any downstream stage.
"""

from src.adapters.base import AdapterError, InputAdapter
from src.adapters.device import DeviceAdapter
from src.adapters.file import FileAdapter
from src.adapters.stream import StreamAdapter
from src.adapters.url import URLAdapter

__all__ = [
    "InputAdapter",
    "AdapterError",
    "FileAdapter",
    "URLAdapter",
    "StreamAdapter",
    "DeviceAdapter",
]
