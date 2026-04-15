---
phase: 05-second-backends-boxer-rtdetr-owlv2
plan: 03
subsystem: infra
tags: [makefile, cli, argparse, checkpoints, huggingface, boxer, rt-detrv2]

# Dependency graph
requires:
  - phase: 05-second-backends-boxer-rtdetr-owlv2
    provides: Plan 05-01 (pyproject deps) + Plan 05-02 (models/ dir scaffold)
provides:
  - Makefile at repo root with 3 .PHONY targets (download-models, download-models-rtdetrv2, download-models-boxer)
  - scripts/download_models.py executable CLI skeleton with --backend + --all flags
  - RT_DETRV2_SHA and BOXER_SHA module constants (verified SHAs from RESEARCH.md D-12)
  - sha256_of() + verify_or_record() helpers for Plan 11 to populate EXPECTED_SHA256
  - Stub functions (download_rtdetrv2 raises NotImplementedError; download_boxer delegates to setup script)
affects:
  - 05-06 (creates scripts/setup_boxer_subprocess.sh that download_boxer() invokes)
  - 05-08 (RT-DETRv2 backend imports RT_DETRV2_SHA/REPO constants from download_models.py or backend module)
  - 05-11 (Wave 3 fills in download_rtdetrv2 body — snapshot_download + ONNX export + sha256 verify)
  - 05-13 (tests/integration/test_download_models.py references the `make download-models` literal)

# Tech tracking
tech-stack:
  added:
    - GNU Make (thin orchestration layer for download targets)
    - Python argparse CLI pattern for multi-backend dispatch
  patterns:
    - "Pattern: Module-level verified SHA constants (RT_DETRV2_SHA, BOXER_SHA) as single source of truth for revision pinning — avoids chicken/egg where backend modules can't import until perception extra installs, but downloads must run first"
    - "Pattern: NotImplementedError with cross-plan tracking reference (Plan 05-11) — gives CI and humans a clear 'not yet implemented, but planned' signal rather than silent pass"
    - "Pattern: sha256 record-on-first-run + verify-on-CI via EXPECTED_SHA256 dict — Plan 11 commits discovered hashes to lock the registry"

key-files:
  created:
    - Makefile
    - scripts/download_models.py
  modified:
    - uv.lock (resync to match Plan 05-01 pyproject perception/dev extras: onnxruntime, optimum, scikit-learn)

key-decisions:
  - "Duplicate RT_DETRV2_SHA/BOXER_SHA between download_models.py and future backend modules rather than import-from — downloads must work BEFORE the perception extra is installed (the downloads ARE what enables those installs). Duplication documented via comment; drift protected by test assertion in Plan 05-08+."
  - "download_boxer() wrapper in Python rather than Makefile-direct-only — this lets `--all` flag dispatch both backends uniformly without Make-level conditionals, and future Plan 11 can add argus-side post-processing (e.g., copy BoxeR ckpts from upstream default location to models/boxer/<sha>/) without Makefile changes."
  - "Minimal Makefile scope (3 download targets only, no test/lint/format targets) — per D-13 planner discretion. Phase 5 is strictly checkpoint pre-fetch; expand only when phases demand it."
  - "NotImplementedError references Plan 05-11 specifically, not just '#TODO' — cross-plan traceability for the verifier."

patterns-established:
  - "SHA-pinned checkpoint contract (D-12): every external checkpoint backend hard-codes a module-level SHA constant; HF loaders pass revision=<sha>, local_files_only=True after first fetch."
  - "Makefile as thin orchestration layer (D-13): targets delegate to Python scripts or shell scripts; no complex logic in Make itself."
  - "Deferred stub pattern: skeleton raises NotImplementedError with explicit plan reference for the implementation plan — predictable failure mode during Wave 0 while locking the interface early."

requirements-completed: [DET-MODELS-07]

# Metrics
duration: 2 min
completed: 2026-04-15
---

# Phase 05 Plan 03: Makefile + download_models.py Skeleton Summary

**Thin repo-root Makefile with 3 .PHONY targets (download-models, download-models-rtdetrv2, download-models-boxer) delegating to an executable argparse CLI skeleton at scripts/download_models.py — locks the SC#4 literal command surface and verified SHA constants for RT-DETRv2 (`5650961749fa93567c0d46fc7f43ea4f9e914107`) and BoxeR (`df474128a76ba42b05bc81feca7ac1a53fab41af`) while deferring real download logic to Plan 05-11 via NotImplementedError.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-15T03:48:02Z
- **Completed:** 2026-04-15T03:50:21Z
- **Tasks:** 2 completed
- **Files created:** 2 (Makefile, scripts/download_models.py)
- **Files modified:** 1 (uv.lock — resync to match Plan 05-01 deps)

## Accomplishments

- **Makefile (Task 1):** 3 TAB-indented `.PHONY` targets at repo root. `download-models` aggregates both sub-targets, `download-models-rtdetrv2` delegates to `uv run python scripts/download_models.py --backend rtdetrv2`, `download-models-boxer` delegates to `bash scripts/setup_boxer_subprocess.sh` (Plan 06 creates the shell script). `make -n download-models` dry-run resolves both sub-target recipes correctly.
- **scripts/download_models.py (Task 2):** Executable (`chmod +x`), shebang `#!/usr/bin/env python3`, argparse CLI with `--backend {rtdetrv2,boxer}` + `--all` flags. Exposes `RT_DETRV2_SHA`, `RT_DETRV2_REPO`, `RT_DETRV2_MODEL_DIR`, `BOXER_SHA`, `BOXER_REPO_URL`, `BOXER_MODEL_DIR`, `EXPECTED_SHA256` module constants. Provides `sha256_of()` + `verify_or_record()` helpers. `download_rtdetrv2()` raises `NotImplementedError` with a Plan 05-11 reference; `download_boxer()` delegates to `scripts/setup_boxer_subprocess.sh` (raises `FileNotFoundError` with a clear Plan 06 hint until that plan lands).
- **CLI behavior verified:** `--help` succeeds (exit 0, mentions `--backend` + `--all`); no-args exits non-zero with message `specify --backend {rtdetrv2,boxer} or --all`; `--backend rtdetrv2` raises the documented `NotImplementedError` with Plan 05-11 tracking reference; `from scripts.download_models import RT_DETRV2_SHA, BOXER_SHA` imports cleanly and prints the two 40-char hex strings.

## Task Commits

1. **Task 1: Create thin repo-root Makefile with three download targets** — `1d3962d` (feat)
2. **Task 2: Create scripts/download_models.py skeleton with argparse CLI and stubbed functions** — `bb12164` (feat, includes uv.lock sync)

_Plan metadata commit will be made by orchestrator after SUMMARY.md creation._

## Files Created/Modified

- `Makefile` (**created**, 13 lines) — 3 `.PHONY` targets for checkpoint pre-fetch (D-13). TAB-indented recipes. SC#4 literal (`make download-models`) preserved exactly.
- `scripts/download_models.py` (**created**, 121 lines, executable) — argparse CLI skeleton. Module-level SHA constants, sha256 helpers, stub downloader functions. Plan 05-11 fills in the real `download_rtdetrv2()` body; Plan 05-06 creates the shell script `download_boxer()` invokes.
- `uv.lock` (**modified**) — Resynced to match Plan 05-01's pyproject additions (onnxruntime, optimum, scikit-learn to `perception`/`dev` extras). Regenerated implicitly by the first `uv run python scripts/download_models.py --help` verification call. See Deviations.

## Decisions Made

1. **SHA constants duplicated between download_models.py and future backend modules** — required because downloads must run BEFORE the perception extra installs (the downloads ARE what unblocks those installs). Single source of truth concern deferred: Plan 05-08+ can add a test that asserts the backend module's `RT_DETRV2_SHA` matches `scripts.download_models.RT_DETRV2_SHA`.
2. **download_boxer() Python wrapper over bash-only** — allows `--all` to dispatch both backends through one Python entry point, and gives Plan 05-11 a hook to add argus-side post-processing (e.g., relocating BoxeR upstream-default checkpoint paths into `models/boxer/<sha>/`) without needing Makefile edits.
3. **Minimal Makefile scope** — per D-13 planner discretion. No test/lint/format targets. Phase 5 is strictly checkpoint pre-fetch; future phases can expand if needed.
4. **NotImplementedError with Plan 05-11 reference rather than a silent no-op** — explicit failure mode so CI catches "skeleton was never filled in" and humans see a clear pointer to the implementation plan.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] uv.lock resync for Plan 05-01's pyproject additions**

- **Found during:** Task 2 (running `uv run python scripts/download_models.py --help` per acceptance criteria)
- **Issue:** Plan 05-01 added `onnxruntime>=1.19.0` to the `perception` extra and `optimum[exporters]>=1.20.0` to the `dev` extra in pyproject.toml but did not regenerate `uv.lock`. The first `uv run` invocation during Plan 05-03's Task 2 verification triggered lock rebuild, producing a dirty working tree that blocked the clean commit state expected by the task commit protocol.
- **Fix:** Committed the regenerated `uv.lock` alongside `scripts/download_models.py` in the Task 2 commit. The lock changes are purely mechanical (adding `onnxruntime`, `optimum`, `scikit-learn` entries) — no new resolver decisions were made by Plan 05-03.
- **Files modified:** `uv.lock`
- **Verification:** `git status` returns clean after commit; `uv run python scripts/download_models.py --help` succeeds without re-resolving.
- **Committed in:** `bb12164` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking).
**Impact on plan:** Lock resync was necessary to leave the worktree in a clean state and let Plan 05-04+ use `uv run` without triggering another resolve. No scope creep; no resolver decisions made — strictly a mechanical catch-up for Plan 05-01's deferred lock update.

### Notes (not deviations)

- **Acceptance criterion `grep -c "NotImplementedError" scripts/download_models.py` returns 1 — actual: 2.** The plan's verbatim code block includes `NotImplementedError` in both the docstring (documentation: "Skeleton raises NotImplementedError with the tracking reference...") and the `raise` statement. The file matches the plan's code block exactly. The grep expectation of `1` is a minor plan-authored miscount — the spirit of the criterion (one `raise` site) is satisfied. No code change made; plan's literal content preserved.

## Issues Encountered

- **uv.lock drift from Plan 05-01:** See Deviation #1 above. Resolved via mechanical re-commit.

## Authentication Gates

None — no external service auth required (Plan 05-11 will exercise HF Hub access; skeleton does not).

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- **Plan 05-04 onward unblocked:** The `make download-models` literal command surface is locked; Wave 2 backend modules can reference `RT_DETRV2_SHA` (either by importing from `scripts.download_models` or by duplicating with a consistency test). Wave 3 Plan 11 has a precise hook point (fill in `download_rtdetrv2()` body) without restructuring.
- **Plan 05-06 creates the expected file:** `scripts/setup_boxer_subprocess.sh`. `download_boxer()` already tolerates its absence with a clear `FileNotFoundError` message pointing to Plan 06.
- **Plan 05-11 tracking:** Both `download_rtdetrv2()` and `EXPECTED_SHA256` await Wave 3 population. The NotImplementedError message references Plan 05-11 and RESEARCH.md "Makefile + download_models.py Contract (D-13)" section for the full implementation spec.
- **No blockers for subsequent plans.**

## Self-Check

Verifying SUMMARY claims against disk/git state...

**Files claimed created:**
- [x] `Makefile` — present (`test -f Makefile` → FOUND)
- [x] `scripts/download_models.py` — present and executable (`test -x` → FOUND)

**Commits claimed:**
- [x] `1d3962d` — `git log` confirms: "feat(05-03): add thin repo-root Makefile for checkpoint pre-fetch (D-13)" → FOUND
- [x] `bb12164` — `git log` confirms: "feat(05-03): add scripts/download_models.py skeleton CLI (D-13)" → FOUND

**Success criteria met:**
- [x] Makefile exists with 3 targets (download-models, download-models-rtdetrv2, download-models-boxer)
- [x] scripts/download_models.py exists, parses as Python, argparse CLI with --backend flag, functions raise NotImplementedError
- [x] RT_DETRV2_SHA and BOXER_SHA constants present with correct values (verified via import)
- [x] SUMMARY.md created (this file)
- [x] Each task committed individually

## Self-Check: PASSED

---
*Phase: 05-second-backends-boxer-rtdetr-owlv2*
*Plan: 03*
*Completed: 2026-04-15*
