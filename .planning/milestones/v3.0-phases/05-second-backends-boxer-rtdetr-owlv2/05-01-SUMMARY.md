---
phase: 05-second-backends-boxer-rtdetr-owlv2
plan: 01
subsystem: infra
tags: [pyproject, dependencies, pytest, gitignore, onnxruntime, optimum, scaffolding]

# Dependency graph
requires:
  - phase: 01-detector-api-foundation
    provides: perception extra layout, dev extra baseline (optional-dependencies skeleton)
  - phase: 02-subprocess-bridge
    provides: SubprocessDetectorBridge skeleton — Wave 1 BoxeR setup will produce subprocess_venvs/boxer/
provides:
  - onnxruntime>=1.19.0 declared in perception extra (D-07)
  - optimum[exporters]>=1.20.0 declared in dev extra (D-06 download-time)
  - slow_boxer + network pytest markers registered ([tool.pytest.ini_options])
  - subprocess_venvs/ excluded from git (D-01)
affects: [05-02, 05-03, 05-04, 05-05, 05-06, 05-07, 05-08, 05-09, 05-10, 05-11, 05-12]

# Tech tracking
tech-stack:
  added: [onnxruntime>=1.19.0, optimum[exporters]>=1.20.0]
  patterns:
    - "Phase-introduced pytest markers registered in [tool.pytest.ini_options] to silence PytestUnknownMarkWarning"
    - "Subprocess venv directories live at repo-root subprocess_venvs/<backend>/ and are gitignored"

key-files:
  created: []
  modified: [pyproject.toml, .gitignore]

key-decisions:
  - "Preserve plan literal optimum[exporters]>=1.20.0 token verbatim; defer optimum/transformers compatibility resolution to Plan 05-04"
  - "Multi-line dev extra reformatting reserved for the optimum addition only — no other version bumps"

patterns-established:
  - "Multi-line list form for optional-dependencies once length > 3 entries (readability + clean diffs for future deps)"
  - "Pytest markers introduced by a phase MUST be registered in pyproject.toml [tool.pytest.ini_options] in the same wave that introduces the marker (Wave 0 here)"

requirements-completed: [DET-MODELS-02, DET-MODELS-03, DET-MODELS-07]

# Metrics
duration: 4min
completed: 2026-04-15
---

# Phase 5 Plan 01: Wave 0 Dependency + Tooling Scaffolding Summary

**ONNX Runtime + optimum extras declared, slow_boxer/network pytest markers registered, subprocess_venvs/ gitignored — pure-config foundation for the entire Phase 5 backend rollout.**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-04-15T03:36:48Z
- **Completed:** 2026-04-15T03:40:32Z
- **Tasks:** 2
- **Files modified:** 2 (pyproject.toml, .gitignore) + 1 created (deferred-items.md)

## Accomplishments

- `pyproject.toml` `[project.optional-dependencies].perception` now lists `onnxruntime>=1.19.0` (the in-process runtime Wave 2 RT-DETRv2 backend will call from `src/perception/backends/rtdetrv2_backend.py`).
- `pyproject.toml` `[project.optional-dependencies].dev` now lists `optimum[exporters]>=1.20.0` for the one-time RT-DETRv2 ONNX export step run by `scripts/download_models.py` (Plan 05-04).
- `pyproject.toml` `[tool.pytest.ini_options]` introduced — registers `slow_boxer` and `network` markers; pytest will no longer emit `PytestUnknownMarkWarning` when Wave 0+ test files apply these markers.
- `.gitignore` excludes `subprocess_venvs/` so the BoxeR isolated venv created by `scripts/setup_boxer_subprocess.sh` (Plan 05-03) does not pollute history.

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend pyproject.toml with ORT + optimum extras and register pytest markers** — `3d8af8e` (chore)
2. **Task 2: Add subprocess_venvs/ to .gitignore** — `33c24b8` (chore)
3. **Deviation log (deferred-items.md)** — `6a8e20d` (chore)

_(Plan-level metadata commit will follow this SUMMARY write.)_

## Files Created/Modified

- `pyproject.toml` — added 1 perception dep, 1 dev dep, multi-lined the dev list, added a new `[tool.pytest.ini_options]` section with two markers.
- `.gitignore` — appended a 2-line section excluding `subprocess_venvs/` with a D-01 reference comment.
- `.planning/phases/05-second-backends-boxer-rtdetr-owlv2/deferred-items.md` (new) — logs the optimum/transformers conflict found during dep validation for Plan 05-04 to resolve.

## Decisions Made

- **Preserve plan literal `optimum[exporters]>=1.20.0` verbatim.** During `uv lock --check` validation, discovered the dep token resolves silently to `optimum==2.1.0` which dropped the `[exporters]` extra (the exporters were extracted to a separate `optimum-onnx` package). Pinning `<2.0` to recover the extra produces a hard resolution conflict against the existing `transformers>=5.3.0` perception pin (optimum 1.x caps `transformers<4.54.0`). Resolution requires architectural choice (downgrade transformers? split dev extra? subprocess-venv the export?) which is out of scope for Wave 0 scaffolding; logged for Plan 05-04 in `deferred-items.md`. Plan 05-01 acceptance criteria all match the literal token, so preserving it keeps grep checks green.
- **Multi-line dev extra reformatting:** plan said "REPLACE the single-line list with multi-line form and APPEND optimum"; no other version bumps were applied to existing dev deps (kept pytest, pytest-timeout, pytest-asyncio at their existing floors).

## Deviations from Plan

### Auto-fixed Issues

None — both tasks executed exactly as written. (The optimum/transformers compatibility issue was DISCOVERED but explicitly NOT auto-fixed; see `deferred-items.md` for the rationale.)

### Discovered Issues Logged for Future Plans

**1. [Discovery — logged for Plan 05-04] optimum[exporters]>=1.20.0 incompatible with transformers>=5.3.0**

- **Found during:** Task 1 verification (`uv lock --check` after pyproject.toml edit)
- **Issue:** Pin token `optimum[exporters]>=1.20.0` resolves to optimum 2.1.0 which has no `exporters` extra (uv emits a silent warning, lockfile still resolves). Adding `<2.0` recovers the extra but the resulting optimum 1.x line caps `transformers<4.54.0`, conflicting with the perception extra's `transformers>=5.3.0`. The `optimum-onnx` package (new home of `main_export` for optimum 2.x) also requires `transformers<4.58`.
- **Why not auto-fixed:** Resolution requires architectural choice across multiple plans (transformers downgrade, dev-extra split, isolated subprocess venv for export, or pre-export + HTTPS fetch). Out of scope for Wave 0 pure-config scaffolding.
- **Action item:** Plan 05-04 (`scripts/download_models.py`) MUST resolve before invoking `optimum.exporters.onnx.main_export`. Three resolution paths documented in `.planning/phases/05-second-backends-boxer-rtdetr-owlv2/deferred-items.md`.
- **Verification:** `uv lock --check` resolves with the pre-existing warning (matches state observed at planning time per RESEARCH § Wave 0 Gaps); no resolution failure with the literal plan token.

---

**Total deviations:** 0 auto-fixed; 1 discovery deferred to Plan 05-04.
**Impact on plan:** Zero scope creep for 05-01. Future plan 05-04 has explicit context to make the architectural call.

## Issues Encountered

- One stale-uv-venv hiccup during exploratory `uv lock --check` runs: a transient `<2.0` upper bound experiment broke `uv run python` until the pyproject was reverted and `uv.lock` was restored via `git checkout`. No artifacts from this experiment remained; final pyproject matches plan literal.

## User Setup Required

None — pure config scaffolding. `uv sync --extra perception --extra dev` will now pull `onnxruntime` and (with the noted compatibility caveat) attempt to pull `optimum`. Plan 05-04 will gate the actual install path.

## Next Phase Readiness

- **Wave 1 (05-02 deps tests, 05-03 BoxeR setup script):** ready — markers registered, subprocess venv path gitignored.
- **Wave 2 (05-04 download_models.py, 05-05/06 backends):** ready in pyproject form; Plan 05-04 has a documented blocker (deferred-items.md) it must address before invoking `optimum.exporters.onnx.main_export`.
- **No code paths exercised this plan** — purely config land.

## Self-Check: PASSED

- pyproject.toml exists: FOUND
- .gitignore contains subprocess_venvs/: FOUND
- deferred-items.md exists: FOUND
- Commit 3d8af8e exists: FOUND
- Commit 33c24b8 exists: FOUND
- Commit 6a8e20d exists: FOUND
- TOML parses: OK
- All 6 plan acceptance criteria pass (grep counts + git check-ignore + tomllib parse)

---
*Phase: 05-second-backends-boxer-rtdetr-owlv2*
*Completed: 2026-04-15*
