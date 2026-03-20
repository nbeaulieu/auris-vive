# Auris Vive — Visual Prototype

Static web prototype: audio playback + per-stem wave visualisation driven by pre-computed curves.

## Setup

```bash
# 1. Export curve data (from repo root, .venv-ml active)
source .venv-ml/bin/activate
python3 scripts/export-curves.py

# 2. Install dependencies
cd docs/proto
npm install

# 3. Run dev server
npm run dev

# 4. Open
open http://localhost:5173
```

Requires at least one song in `test_audio/` with computed curves (`test_audio/<slug>/curves/`).
