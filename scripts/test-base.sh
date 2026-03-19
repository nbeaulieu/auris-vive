#!/bin/bash
# test-base.sh — run test suite in the base environment (.venv, Python 3.13)
# Usage: ./scripts/test-base.sh

set -e
cd "$(dirname "$0")/.."

echo "▸ activating .venv (Python 3.13)"
source .venv/bin/activate

echo "▸ running tests"
pytest

echo "✓ base env tests passed"
