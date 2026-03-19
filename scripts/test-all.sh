#!/bin/bash
# test-all.sh — run test suite in both environments sequentially
# Usage: ./scripts/test-all.sh

set -e
cd "$(dirname "$0")/.."

./scripts/test-base.sh
./scripts/test-ml.sh

echo ""
echo "✓ all environments passed"
