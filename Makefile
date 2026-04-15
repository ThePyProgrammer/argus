# Phase 5 (D-13): Checkpoint pre-fetch targets. `make download-models` is the
# SC#4 literal — do NOT rename. Python-side logic lives in scripts/download_models.py;
# BoxeR weight fetch runs inside the subprocess venv (setup_boxer_subprocess.sh).

.PHONY: download-models download-models-rtdetrv2 download-models-boxer

download-models: download-models-rtdetrv2 download-models-boxer

download-models-rtdetrv2:
	uv run python scripts/download_models.py --backend rtdetrv2

download-models-boxer:
	bash scripts/setup_boxer_subprocess.sh
