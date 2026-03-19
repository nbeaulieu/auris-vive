"""
Root conftest.py — makes `src` importable as a top-level package during pytest.

Why this exists
---------------
The monorepo layout places source under `src/`, which is not on sys.path by
default.  Adding it here means `from src.pipeline.ingest import ...` resolves
correctly for every test in the suite without requiring an editable install.

This file must live at the repo root (alongside `pyproject.toml`), not inside
`tests/`.  pytest discovers it automatically before collecting any tests.
"""

import sys
from pathlib import Path

# Insert repo root so both `src.*` and (eventually) `tests.*` are importable.
sys.path.insert(0, str(Path(__file__).parent))
