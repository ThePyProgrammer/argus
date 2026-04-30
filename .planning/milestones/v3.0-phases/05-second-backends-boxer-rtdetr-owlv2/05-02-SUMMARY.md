---
phase: 05-second-backends-boxer-rtdetr-owlv2
plan: 02
subsystem: docs
tags: [licenses, spdx, models-dir, boxer, cc-by-nc, d-11, d-14]

# Dependency graph
requires:
  - phase: 05-second-backends-boxer-rtdetr-owlv2
    provides: Plan 05-01 — pyproject.toml perception/dev extras, subprocess_venvs/ gitignored, optimum conflict logged
provides:
  - LICENSES.md at repo root — SPDX inventory for every runtime dep + BoxeR CC-BY-NC-4.0 row + NC Compliance Mechanism section
  - LICENSES.md — separate "Indirect / Upstream Dependencies (NOT SHIPPED by argus)" subsection with OWLv2 [NOT-SHIPPED] row (TODO(plan-06) verify-or-delete)
  - models/.gitkeep — empty placeholder that pins the models/ directory in git
  - models/README.md — documents the D-11 models/<backend-slug>/<sha>/<artifact> layout with concrete rtdetrv2/<RT_DETRV2_SHA>/ + boxer/<BOXER_SHA>/ trees
affects:
  - 05-03 (Wave 0 SC-grep tests — will grep LICENSES.md for CC-BY-NC-4.0 + NC Compliance Mechanism)
  - 05-04 (scripts/download_models.py — writes under models/rtdetrv2/<sha>/)
  - 05-06 (BoxeR subprocess setup — writes under models/boxer/<sha>/, must confirm/kill OWLv2 row)
  - 05-11 (sha256 verification — reads EXPECTED_SHA256 constants, honors immutability invariant)
  - all future v3.0 phases: LICENSES.md is the canonical license inventory — new runtime deps must be appended

# Tech tracking
tech-stack:
  added: []  # Pure docs + scaffolding plan — no runtime code, no new libs
  patterns:
    - "LICENSES.md = single source of truth for SPDX identifiers; capability dict renders in-UI pills"
    - "Indirect/Upstream subsection keeps the main Runtime Dependencies table honest (only user-facing deps)"
    - "models/<backend-slug>/<sha>/<artifact> layout is backend-name-owned and SHA-immutable"

key-files:
  created:
    - LICENSES.md
    - models/.gitkeep
    - models/README.md
  modified: []

key-decisions:
  - "OWLv2 row lives ONLY in Indirect/Upstream subsection — main Runtime Deps table stays user-facing; per D-10 OWLv2 is dropped as a selectable backend"
  - "TODO(plan-06) note embedded in LICENSES.md: if BoxeR does not actually load OWLv2 at runtime, delete the row during Plan 06 execution"
  - "Phase 5 does NOT add per-file .gitignore entries for rtdetrv2/ or boxer/ checkpoints (<200 MB combined, SHA-pinned paths are cache-friendly)"

patterns-established:
  - "LICENSES.md at repo root with SPDX | Scope | Upstream | Note columns + explicit NC Compliance Mechanism + Audit checklist sections"
  - "models/README.md documents directory contract; any writer outside scripts/download_models.py or scripts/setup_boxer_subprocess.sh is a violation"

requirements-completed: [DET-MODELS-08, DET-MODELS-07]

# Metrics
duration: 2min
completed: 2026-04-15
---

# Phase 5 Plan 02: LICENSES inventory + models/ layout scaffolding Summary

**LICENSES.md shipped with BoxeR CC-BY-NC-4.0 row + 19 other runtime deps + Indirect/Upstream subsection for OWLv2 [NOT-SHIPPED]; models/ directory pinned via .gitkeep with README documenting the D-11 `<backend-slug>/<sha>/<artifact>` layout.**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-04-15T03:43:42Z
- **Completed:** 2026-04-15T03:45:22Z
- **Tasks:** 2
- **Files created:** 3

## Accomplishments

- LICENSES.md at repo root — 20-row SPDX table covering every runtime dep (YOLOv11/AGPL-3.0, RT-DETRv2/Apache-2.0, BoxeR/CC-BY-NC-4.0, ONNX Runtime/MIT, pyzmq/LGPL+BSD, Open3D/MIT, PyTorch/BSD-3, numpy, scipy, opencv, scikit-learn, MuJoCo, FastAPI, uvicorn, websockets, etc.)
- LICENSES.md — NC Compliance Mechanism section explicitly documents the capability-badge surfacing path (`BoxeRBackend.CAPABILITIES["license"] = "CC-BY-NC-4.0"` → DetectorDropdown pill)
- LICENSES.md — separate "Indirect / Upstream Dependencies (NOT SHIPPED by argus)" subsection with the OWLv2 [NOT-SHIPPED] row and TODO(plan-06) delete-if-unused note
- LICENSES.md — Audit checklist as a forcing function for future runtime-dep additions
- models/.gitkeep — 0-byte placeholder keeps `models/` tracked even if all artifacts are gitignored per-file
- models/README.md — documents the D-11 `models/<backend-slug>/<sha>/<artifact>` layout with concrete sub-trees for rtdetrv2/<RT_DETRV2_SHA>/ (pt/, model.onnx, config.json, preprocessor_config.json) and boxer/<BOXER_SHA>/ (boxernet/, dinov3/, owlv2/ internal-only), invariants, and writer whitelist (scripts/download_models.py + scripts/setup_boxer_subprocess.sh)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create LICENSES.md at repo root with full SPDX table** — `c2aef89` (docs)
2. **Task 2: Create models/ directory scaffolding (gitkeep + README)** — `d0c9545` (docs)

## Files Created/Modified

- `LICENSES.md` (created, 52 lines) — Third-Party License Inventory with Runtime Dependencies table, Indirect/Upstream Dependencies subsection, NC Compliance Mechanism, Audit checklist
- `models/.gitkeep` (created, 0 bytes) — directory pinning placeholder
- `models/README.md` (created, 55 lines) — D-11 layout docs + invariants + writer whitelist

## Decisions Made

- **OWLv2 placement:** Kept in a separate "Indirect / Upstream Dependencies (NOT SHIPPED by argus)" subsection rather than the main Runtime Dependencies table. Rationale: per Phase 5 D-10, OWLv2 is dropped as a user-selectable backend but may still be loaded transitively inside the BoxeR subprocess venv — auditors reading the file need to see which licenses argus ships as a user-facing dep vs. which it only pulls in transitively. A TODO(plan-06) note flags this row for verify-or-delete during BoxeR worker execution.
- **No per-file gitignore entries added for rtdetrv2/ or boxer/:** Phase 5 leaves the .gitignore convention as v2.0 established (specific large binaries like ORBvoc are excluded by name). Combined RT-DETRv2 + BoxeR artifact size (<200 MB) is not large enough to warrant directory-wide exclusion, and SHA-pinned paths are cache-friendly.

## Deviations from Plan

None — plan executed exactly as written. Task 1's file content and Task 2's file content both matched the plan's verbatim specification (LICENSES.md 52 lines, models/README.md 55 lines). All `<verify>` and `<acceptance_criteria>` checks returned the expected values on the first run.

## Issues Encountered

- **Worktree base drift:** On executor entry, `git merge-base HEAD <EXPECTED_BASE>` returned `fc24a5a` (state-only commit from phase planning) rather than the expected `f8fc12f` (Plan 05-01 completion). HEAD was behind the expected base by 4 commits (Plan 05-01 commits that ran in a sibling worktree). Resolved with `git reset --hard f8fc12fefaf729707369ba89bbad5057e643bdf9` — working tree was clean so no work was lost. After reset, proceeded normally. Not a deviation from plan execution; a branch-state anomaly resolved per the `<worktree_branch_check>` protocol.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- **Plan 05-03 (Wave 0 SC-grep tests):** LICENSES.md strings `CC-BY-NC-4.0`, `NC Compliance Mechanism`, `AGPL-3.0`, `Apache-2.0`, `Indirect / Upstream Dependencies (NOT SHIPPED by argus)`, and `**[NOT-SHIPPED]** OWLv2` are all present and greppable. The DET-MODELS-08 invariant test will pass.
- **Plan 05-04 (scripts/download_models.py):** models/ directory exists with documented layout; download script can create `models/rtdetrv2/<RT_DETRV2_SHA>/pt/` and `models/rtdetrv2/<RT_DETRV2_SHA>/model.onnx` without ambiguity about the target tree.
- **Plan 05-06 (BoxeR subprocess setup):** models/boxer/<BOXER_SHA>/ path is documented; MUST re-evaluate the OWLv2 row in LICENSES.md (Indirect subsection) — delete it if the BoxeR worker does not actually instantiate OWLv2 at runtime. The TODO(plan-06) note inside LICENSES.md carries this instruction forward.
- **Plan 05-11 (sha256 verification):** models/README.md's immutability invariant ("Artifacts inside `<sha>/` are immutable for the lifetime of that SHA") is the contract that sha256 verification enforces.
- No blockers. Pure docs/scaffolding plan with zero runtime-code risk.

---

## Self-Check: PASSED

Verified all claims:

- FOUND: `/home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-ae390b4e/LICENSES.md` (52 lines)
- FOUND: `/home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-ae390b4e/models/.gitkeep` (0 bytes)
- FOUND: `/home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-ae390b4e/models/README.md` (55 lines)
- FOUND: commit `c2aef89` (Task 1: LICENSES.md)
- FOUND: commit `d0c9545` (Task 2: models/ scaffolding)
- Verified `grep -q "CC-BY-NC-4.0" LICENSES.md` passes, count = 3
- Verified OWLv2 appears 0 times in main Runtime Dependencies table, 1 time in Indirect subsection

---

*Phase: 05-second-backends-boxer-rtdetr-owlv2*
*Completed: 2026-04-15*
