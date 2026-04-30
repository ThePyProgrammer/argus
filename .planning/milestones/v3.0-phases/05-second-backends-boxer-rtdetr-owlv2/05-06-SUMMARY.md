---
phase: 05-second-backends-boxer-rtdetr-owlv2
plan: 06
subsystem: perception
tags: [boxer, subprocess, zmq, msgpack, 3d-obb, venv-bootstrap, scipy, uv]

# Dependency graph
requires:
  - phase: 02-detection-pluggability
    provides: SubprocessDetectorBridge wire protocol (D-17) + echo_detector_worker.py structural template
  - phase: 05-second-backends-boxer-rtdetr-owlv2
    provides: Plan 05-02 models/ directory layout (D-11), Plan 05-05 bridge typed exceptions + handshake, Plan 05-03 Makefile target download-models-boxer
provides:
  - scripts/boxer_worker.py (Phase 5 D-02 worker — connect-after-load readiness, boxes_3d wire schema, Phase 1 D-10 carve-out documented)
  - scripts/setup_boxer_subprocess.sh (idempotent venv bootstrap — uv venv 3.12, pinned BoxeR SHA, EGL_PLATFORM=surfaceless, rollback trap)
affects:
  - plan 05-08 (BoxeRBackend composer consumes boxes_3d reply schema via OrientedBox3D.to_wire())
  - plan 05-11 (manual/CI exercise of setup_boxer_subprocess.sh network fetch)

# Tech tracking
tech-stack:
  added:
    - subprocess_venvs/boxer/ convention (venv-per-incompatible-backend isolation)
    - BoxeR git SHA pin (df474128a76ba42b05bc81feca7ac1a53fab41af)
  patterns:
    - "Connect-after-load readiness: worker blocks on model load BEFORE sock.connect() so bridge handshake treats socket-ready as worker-ready (Open Risk #3 mitigation)"
    - "Phase 1 D-10 CARVE-OUT: cross-venv subprocess workers may construct wire-format quaternions; composer re-hydrates via OrientedBox3D.to_wire() preserving invariant in main process"
    - "Idempotent venv bootstrap via .ready marker (D-01) + trap cleanup EXIT rollback"

key-files:
  created:
    - scripts/boxer_worker.py
    - scripts/setup_boxer_subprocess.sh

key-decisions:
  - "boxer_worker.py uses scipy.spatial.transform.Rotation.from_matrix(...).as_quat() to produce xyzw wire quaternions — scoped exception to Phase 1 D-10 documented in module docstring and per-use comment"
  - "Worker exits with code 2 + sentinel reply when BoxeR Python API import fails (Open Risk #1 fallback) so bridge surfaces SubprocessDiedError with context"
  - "setup_boxer_subprocess.sh exports EGL_PLATFORM=surfaceless before uv pip install to mitigate BoxeR moderngl headless import path (Open Risk #2)"
  - "Post-copy fallback in setup script handles the case where BoxeR's own download_ckpts.sh ignores CKPTS_DIR/BOXER_CKPTS env overrides"

patterns-established:
  - "Foreign-venv subprocess worker scripts are carved out of the Phase 1 D-10 quaternion-construction-site invariant; the rule governs code in argus main process only"
  - "Idempotency gate MUST be at the top of bootstrap scripts — before any side effects — with a literal .ready marker check"
  - "Rollback on partial failure via `trap cleanup EXIT` — disable explicitly with `trap - EXIT` once success is committed"

requirements-completed: [DET-MODELS-03, DET-MODELS-07]

# Metrics
duration: ~12min
completed: 2026-04-15
---

# Phase 5 Plan 6: BoxeR Subprocess Support Files Summary

**Ships scripts/boxer_worker.py (ZMQ PAIR worker with D-02 boxes_3d reply schema + Phase 1 D-10 carve-out) and scripts/setup_boxer_subprocess.sh (idempotent uv-venv bootstrap pinned to BoxeR SHA df474128).**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-04-15T04:03:00Z
- **Completed:** 2026-04-15T04:15:03Z
- **Tasks:** 2
- **Files created:** 2

## Accomplishments

- `scripts/boxer_worker.py` — runs inside subprocess_venvs/boxer/ Python, blocks on model load before sock.connect(), emits Phase 5 D-02 reply schema with `boxes_3d` list (xyzw quaternions + FULL extents), has Open Risk #1 diagnostic fallback (exit code 2 + sentinel reply if BoxeR public API mismatch).
- `scripts/setup_boxer_subprocess.sh` — idempotent via `.ready` marker (D-01 literal), pins BoxeR git SHA, creates uv-managed Python 3.12 venv, clones+checks-out, `uv pip install -e`, fetches checkpoints into `models/boxer/<BOXER_SHA>/` (D-11 layout), rollback trap on partial failure, EGL_PLATFORM=surfaceless mitigation for moderngl headless (Open Risk #2).
- Phase 1 D-10 carve-out documented in the worker's module docstring as a scoped exception to the "OrientedBox3D is the sole quaternion construction site" invariant, preserving the invariant in the argus main process via composer re-hydration path (`OrientedBox3D.to_wire()` in Plan 08).

## Task Commits

1. **Task 1: scripts/boxer_worker.py** - `5b7fe5d` (feat) — 228-line ZMQ PAIR worker with connect-after-load readiness, D-02 schema, Open Risk #1 fallback, Phase 1 D-10 carve-out doc.
2. **Task 2: scripts/setup_boxer_subprocess.sh** - `c3f491c` (feat) — 86-line idempotent bash bootstrap: uv venv 3.12, git clone + checkout SHA, uv pip install -e, ckpt fetch with post-copy fallback, rollback on failure.

## Files Created

- `scripts/boxer_worker.py` — executable Python script (`#!/usr/bin/env python3`), parses cleanly via `ast.parse`. Runs inside `subprocess_venvs/boxer/bin/python` (not main venv). Wire schema: `{ts, inference_ms, n_det, classes, scores, bboxes, boxes_3d}` where `boxes_3d` is a list of `{tx, ty, tz, qx, qy, qz, qw, w, h, d}` dicts (FULL extents — composer halves for `OrientedBox3D.half_extents`).
- `scripts/setup_boxer_subprocess.sh` — executable bash script, passes `bash -n` syntax check. Invoked by `make download-models-boxer`. Hardcodes `BOXER_SHA="df474128a76ba42b05bc81feca7ac1a53fab41af"` (verified via RESEARCH.md GitHub API reference). Has `set -euo pipefail` + `trap cleanup EXIT`.

## Decisions Made

Followed plan verbatim for both files — the plan's `<action>` blocks specified the EXACT file contents (byte-for-byte with indentation + comments). Verification criteria include grep counts on load-bearing literal strings (e.g., `"Phase 1 D-10 CARVE-OUT"` ≥ 2, `"invariant is preserved in the argus main process"` = 1), so the plan author intentionally constrained the text. No implementation discretion exercised.

## Deviations from Plan

None — plan executed exactly as written. Both files created with the exact content specified in the plan's `<action>` blocks, made executable, and all acceptance criteria grep-verified.

---

**Total deviations:** 0
**Impact on plan:** Clean execution; verification criteria met exactly as authored.

## Issues Encountered

- **Worktree base mismatch on start:** initial HEAD was `10202b7` (merge commit ancestor of expected base). Per the `<worktree_branch_check>` directive, performed `git reset --hard f70ec016ae21b070d1808c4cf8a63b32503c032d` to land on the expected Plan 05-05 tip. No Plan 06 content was affected — the reset only advanced forward onto the canonical base.
- **Pre-existing pytest collection errors** (`ModuleNotFoundError: No module named 'fastapi'`, `torch`, `open3d`) in unrelated test modules — already documented in `deferred-items.md` under "Plan 05-05: Pre-existing fastapi / torch import errors outside scope." Plan 06 adds 2 standalone scripts with no imports into the main src/ tree, so these pre-existing failures are not regressions. The narrow per-file verification (`bash -n`, `ast.parse`, grep counts) passes cleanly.

## Verification Evidence

### Task 1 (scripts/boxer_worker.py)

```
uv run python -c "import ast; ast.parse(open('scripts/boxer_worker.py').read())"  # exit 0
head -1 scripts/boxer_worker.py                                                   # #!/usr/bin/env python3
grep -c 'Phase 1 D-10 CARVE-OUT'                                                  # 3  (≥ 2 required)
grep -c 'invariant is preserved in the argus main process'                        # 1  (exact)
grep -c 'boxes_3d'                                                                # 8  (≥ 2 required)
grep -c 'BOXER_SHA = "df474128a76ba42b05bc81feca7ac1a53fab41af"'                  # 1  (exact)
grep -c 'sock.connect'                                                            # 1  (exact — readiness pattern)
grep -c 'from scipy.spatial.transform import Rotation'                            # 1  (exact)
grep -c '"w": float(b.extent'                                                     # 1  (exact — D-02 FULL-extent trail)
grep -c 'Open Risk #1'                                                            # 3  (≥ 1 required)
grep -c 'D-02'                                                                    # 5  (≥ 2 required)
test -x scripts/boxer_worker.py                                                   # OK (chmod +x applied)
```

### Task 2 (scripts/setup_boxer_subprocess.sh)

```
bash -n scripts/setup_boxer_subprocess.sh                                         # exit 0
head -1                                                                           # #!/usr/bin/env bash
grep -c 'BOXER_SHA="df474128a76ba42b05bc81feca7ac1a53fab41af"'                    # 1
grep -c 'set -euo pipefail'                                                       # 1
grep -c '\[ -f "\$VENV_DIR/\.ready" \]'                                           # 1 (idempotency gate)
grep -c 'uv venv --python 3.12'                                                   # 1
grep -c 'git -C .* checkout .*BOXER_SHA'                                          # 1
grep -c 'EGL_PLATFORM'                                                            # 2 (export + comment)
grep -c 'touch .*\.ready'                                                         # 1 (ready marker post-success)
grep -c 'trap cleanup EXIT'                                                       # 1
test -x scripts/setup_boxer_subprocess.sh                                         # OK
```

## User Setup Required

None at execution time. The setup script performs network clone + multi-GB checkpoint fetch, but that is deferred to the user's `make download-models-boxer` step post-merge (which Plan 03 already wired and Plan 11 will exercise in CI).

## Next Phase Readiness

- **Plan 05-07 (Wave 2, depends_on: 05-06):** Can compose the typed bridge (Plan 05-05) with this worker in test scaffolding without the venv actually existing — `bash -n` + `ast.parse` already confirm surface correctness.
- **Plan 05-08 (BoxeRBackend composer, depends_on: 05-06):** Will read `boxes_3d` from the worker's reply dict and call `OrientedBox3D(...)` — the composer divides `w/h/d` by 2 to convert D-02 FULL extents to `OrientedBox3D.half_extents`. The composer is the re-hydration site that preserves the Phase 1 D-10 invariant in the argus main process.
- **Plan 05-11 (integration):** When the user runs `make download-models-boxer`, the idempotent script will (1) clone BoxeR at the pinned SHA, (2) install into `subprocess_venvs/boxer/`, (3) fetch checkpoints into `models/boxer/<SHA>/`, (4) touch `.ready`. Subsequent invocations short-circuit at the idempotency gate.

## Self-Check: PASSED

- `scripts/boxer_worker.py` — FOUND (228 lines, executable, parses cleanly)
- `scripts/setup_boxer_subprocess.sh` — FOUND (86 lines, executable, `bash -n` clean)
- Commit `5b7fe5d` — FOUND (`feat(05-06): add BoxeR ZMQ PAIR worker script (D-02 schema)`)
- Commit `c3f491c` — FOUND (`feat(05-06): add idempotent BoxeR subprocess venv bootstrap script`)
- All 12 Task 1 acceptance criteria pass
- All 12 Task 2 acceptance criteria pass
- Plan-level `<success_criteria>` met

---
*Phase: 05-second-backends-boxer-rtdetr-owlv2*
*Plan: 06*
*Completed: 2026-04-15*
