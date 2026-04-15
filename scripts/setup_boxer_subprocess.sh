#!/usr/bin/env bash
# Phase 5 (D-01): idempotent BoxeR subprocess venv bootstrap.
#
# Creates subprocess_venvs/boxer/ with its own Python 3.12, clones
# facebook/boxer at pinned SHA, installs deps via uv, downloads checkpoints
# into models/boxer/<BOXER_SHA>/ (D-11 layout).
#
# Invoked by: `make download-models-boxer` (repo root)
#
# Idempotency: checks subprocess_venvs/boxer/.ready marker at top; if present,
# exits 0 immediately (no re-clone, no re-install). Safe to run multiple times.
#
# Rollback: if any step fails after VENV_DIR is created but before .ready is
# touched, the ERR trap removes the partial venv so the next invocation
# starts clean.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$REPO_ROOT/subprocess_venvs/boxer"
BOXER_REPO_DIR="$VENV_DIR/repo"
BOXER_SHA="df474128a76ba42b05bc81feca7ac1a53fab41af"   # [VERIFIED: GitHub API 2026-04-15]
BOXER_REPO_URL="https://github.com/facebookresearch/boxer"
MODELS_DIR="$REPO_ROOT/models/boxer/$BOXER_SHA"

# ---- Idempotency gate (D-01 literal) ----
if [ -f "$VENV_DIR/.ready" ]; then
  echo "[setup_boxer] $VENV_DIR/.ready exists; skipping."
  exit 0
fi

# ---- Rollback on partial failure ----
cleanup() {
  local code=$?
  if [ "$code" -ne 0 ]; then
    echo "[setup_boxer] FAILED (exit $code). Removing partial venv: $VENV_DIR" >&2
    rm -rf "$VENV_DIR"
  fi
  exit "$code"
}
trap cleanup EXIT

echo "[setup_boxer] Creating subprocess venv at $VENV_DIR"
mkdir -p "$VENV_DIR"

# ---- Step 1: uv-managed venv on Python 3.12 (BoxeR's required interpreter) ----
uv venv --python 3.12 "$VENV_DIR"
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# ---- Step 2: Clone BoxeR at pinned SHA ----
echo "[setup_boxer] Cloning $BOXER_REPO_URL into $BOXER_REPO_DIR"
git clone "$BOXER_REPO_URL" "$BOXER_REPO_DIR"
git -C "$BOXER_REPO_DIR" checkout "$BOXER_SHA"

# ---- Step 3: Install BoxeR + its deps via uv ----
# BoxeR ships a pyproject.toml (verified) so editable install suffices.
# EGL_PLATFORM=surfaceless mitigates BoxeR's moderngl headless import path
# (Open Risk #2 per 05-RESEARCH.md).
echo "[setup_boxer] Installing BoxeR (editable) via uv pip"
export EGL_PLATFORM="surfaceless"
uv pip install -e "$BOXER_REPO_DIR"

# ---- Step 4: Fetch checkpoints into models/boxer/<SHA>/ (D-11 layout) ----
echo "[setup_boxer] Fetching checkpoints into $MODELS_DIR"
mkdir -p "$MODELS_DIR"
if [ -f "$BOXER_REPO_DIR/scripts/download_ckpts.sh" ]; then
  # BoxeR's own fetcher. Override target via env var if supported, otherwise
  # post-copy from the default location.
  ( cd "$BOXER_REPO_DIR" && \
    CKPTS_DIR="$MODELS_DIR" BOXER_CKPTS="$MODELS_DIR" \
    bash scripts/download_ckpts.sh )
  # Post-copy fallback: if BoxeR's script ignored our env vars and dumped
  # to its own ckpts/ dir, move the artifacts.
  if [ -d "$BOXER_REPO_DIR/ckpts" ] && [ -z "$(ls -A "$MODELS_DIR" 2>/dev/null)" ]; then
    echo "[setup_boxer] Post-copying ckpts/ -> $MODELS_DIR"
    cp -r "$BOXER_REPO_DIR/ckpts/." "$MODELS_DIR/"
  fi
else
  echo "[setup_boxer] WARNING: $BOXER_REPO_DIR/scripts/download_ckpts.sh not found. Manual ckpt fetch required." >&2
fi

# ---- Step 5: Touch ready marker — only on full success ----
touch "$VENV_DIR/.ready"
trap - EXIT   # disable rollback; success is committed
echo "[setup_boxer] ready. Marker: $VENV_DIR/.ready"
