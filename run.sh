#!/usr/bin/env bash
# Run the project inside nix develop shell with proper LD_LIBRARY_PATH
# Usage: ./run.sh --control random --max-steps 200
exec nix develop --command bash -c "uv run --python 3.12 python -m src.main $*"
