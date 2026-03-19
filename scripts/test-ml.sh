#!/bin/bash
# test-ml.sh — run test suite in the ML environment (.venv-ml, Python 3.11)
# Usage: ./scripts/test-ml.sh

set -e
cd "$(dirname "$0")/.."

echo "▸ activating .venv-ml (Python 3.11)"
source .venv-ml/bin/activate

echo "▸ running tests"
pytest

echo "✓ ml env tests passed"
