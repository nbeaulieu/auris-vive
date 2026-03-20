# Auris Vive — development tasks
# Usage: make <target>
# Run 'make' or 'make help' to see all targets.

VENV     := .venv-ml/bin/activate
PYTHON   := . $(VENV) && python3
DEVICE   ?= mps

.PHONY: help test test-base test-ml ui dev build export analyse transcribe \
        stems-all clean-stems commit

# ── Help ──────────────────────────────────────────────────────────────────────

help:
	@echo ""
	@echo "  Auris Vive"
	@echo ""
	@echo "  Pipeline"
	@echo "    make ui           Launch the pipeline UI (grab/stems/analyse/export)"
	@echo "    make stems-all    Re-run stems for all songs (force)"
	@echo "    make analyse      Re-analyse all songs with stems (adds pitch curves)"
	@echo "    make export       Export all curves + audio to docs/proto/public/data/"
	@echo "    make transcribe   Transcribe vocals for all songs (requires Whisper)"
	@echo ""
	@echo "  Web prototype"
	@echo "    make dev          Start Vite dev server at localhost:5173"
	@echo "    make build        Build prototype for GitHub Pages"
	@echo ""
	@echo "  Tests"
	@echo "    make test         Run full test suite in both environments"
	@echo "    make test-base    Run tests in .venv (Python 3.13)"
	@echo "    make test-ml      Run tests in .venv-ml (Python 3.11)"
	@echo ""
	@echo "  Other"
	@echo "    make clean-stems  Delete all stems/curves (keeps clips)"
	@echo ""

# ── Pipeline ──────────────────────────────────────────────────────────────────

ui:
	. $(VENV) && AURIS_DEVICE=$(DEVICE) python3 scripts/pipeline-ui.py

analyse:
	. $(VENV) && bash scripts/run-analyse.sh

export:
	. $(VENV) && python3 scripts/export-curves.py

transcribe:
	@echo "▸ transcribing vocals for all songs..."
	@. $(VENV) && for slug in $$(python3 -c \
		"import json; [print(s['slug']) for s in json.load(open('test_audio/songs.json'))]"); do \
		if [ -f "test_audio/$$slug/stems/vocals.flac" ]; then \
			echo "  $$slug"; \
			bash scripts/transcribe-vocals.sh $$slug; \
		fi; \
	done

stems-all:
	@echo "▸ force re-running stems for all songs..."
	@. $(VENV) && python3 -c " \
import json, subprocess, os; \
songs = json.load(open('test_audio/songs.json')); \
env = {**os.environ, 'AURIS_DEVICE': '$(DEVICE)'}; \
[subprocess.run(['bash', 'scripts/run-stems.sh', \
	f'test_audio/{s[\"slug\"]}/clip.wav', s['slug'], '--force'], env=env) \
	for s in songs if (lambda p: p.exists())(__import__('pathlib').Path(f'test_audio/{s[\"slug\"]}/clip.wav'))]"

# ── Web prototype ─────────────────────────────────────────────────────────────

dev:
	cd docs/proto && npm run dev

build:
	cd docs/proto && npm run build

# ── Tests ─────────────────────────────────────────────────────────────────────

test:
	bash scripts/test-all.sh

test-base:
	bash scripts/test-base.sh

test-ml:
	bash scripts/test-ml.sh

# ── Cleanup ───────────────────────────────────────────────────────────────────

clean-stems:
	@echo "▸ removing stems and curves (keeping clips)..."
	@find test_audio -name "stems" -type d -exec rm -rf {} + 2>/dev/null || true
	@find test_audio -name "curves" -type d -exec rm -rf {} + 2>/dev/null || true
	@echo "✓ done"
