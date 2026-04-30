---
phase: 06-detection-metrics-and-mujoco-gt
plan: 07
subsystem: data
tags: [perception, metrics, mujoco, ground-truth, yaml, scene-config]

# Dependency graph
requires:
  - phase: 06
    provides: "RESEARCH §Example 2 verified live body names + geom_xpos values"
provides:
  - "data/scenes/scene_office1_gt.yaml — COCO class (chair, dining_table) → MuJoCo body-name mapping for scene_office1.xml"
  - "Canonical mapping file consumed by MuJoCoGTExtractor(mapping_yaml_path, mj_model, mj_data)"
affects:
  - "06-08 MuJoCoGTExtractor construction + graceful degradation"
  - "06-10 coordinator pump (loads mapping at boot via scene_office1_gt.yaml path)"
  - "DET-METRICS-02 (MuJoCo ground-truth metrics)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Scene-paired ground-truth data: `<scene>.xml` + `<scene>_gt.yaml` colocated under `data/scenes/`"
    - "Every mapped body pre-validated via `mj_name2id` + first-geom check before commit"

key-files:
  created:
    - "data/scenes/scene_office1_gt.yaml"
  modified: []

key-decisions:
  - "Use `data.geom_xpos[first_geom_of_body]` (RESEARCH F1) — body-origin is (0,0,0) for every labeled body in this scene; `data.xpos` would return zeros"
  - "Ship chair + dining_table only in v3.0; tv/couch/etc commented out until SC#2 is green for chair (research recommendation)"
  - "Keep inline `geom_xpos ~ (x,y,z)` comments on every entry as a human-debugging aid at load time"

patterns-established:
  - "Scene-paired ground-truth YAML: `data/scenes/<scene>_gt.yaml` mirrors `<scene>.xml`"
  - "Live-validated body-name lists (mj_name2id + geom check) at commit time catch typos before runtime"

requirements-completed: [DET-METRICS-02]

# Metrics
duration: 2min
completed: 2026-04-15
---

# Phase 6 Plan 7: scene_office1_gt.yaml Summary

**COCO→MuJoCo ground-truth mapping file — chair (3 bodies) + dining_table (4 bodies) validated live against scene_office1.xml via mj_name2id + first-geom check**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-04-15T07:43:39Z
- **Completed:** 2026-04-15T07:45:20Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- Committed `data/scenes/scene_office1_gt.yaml` with 2 COCO classes / 7 MuJoCo body names
- Every body verified to resolve via `mj_name2id` and have ≥1 geom (acceptance criteria pass)
- Inline `geom_xpos ~ (x,y,z)` comments preserved per RESEARCH F1 — consumers know to read `data.geom_xpos`, not `data.xpos`
- Optional/deferred classes (tv, couch, potted_plant, book, vase, cup, bottle) documented as YAML comments for future extension

## Task Commits

Each task was committed atomically:

1. **Task 1: Write scene_office1_gt.yaml + validate every body resolves** — `2d5578c` (feat)

**Plan metadata:** pending final commit (this SUMMARY)

## Files Created/Modified
- `data/scenes/scene_office1_gt.yaml` — canonical COCO-class → MuJoCo body-name mapping for `scene_office1.xml`; consumed by Plan 08's `MuJoCoGTExtractor` and loaded at coordinator boot (Plan 10)

## Decisions Made
- **geom_xpos over xpos:** Every labeled body in `scene_office1.xml` has body-origin at world (0,0,0). Extractor MUST read `data.geom_xpos[first_geom_of_body]`. YAML header comment and inline comments make this explicit for future readers. (RESEARCH F1)
- **Scope: chair + dining_table only.** RESEARCH flagged `tv` as lower-confidence (class 62 vs laptop 63 collisions) and confirmed no couch/plant/book/vase/cup/bottle present. Ship the verified two classes; the rest stay as YAML comments for future turn-on once SC#2 passes.
- **Inline geom_xpos FYI comments:** Not strictly required at runtime, but kept because they give a debugger a ground-truth coordinate to sanity-check `data.geom_xpos[...]` lookups at boot without re-running `mj_forward`.

## Deviations from Plan

None — plan executed exactly as written. The plan's <interfaces> block was used verbatim, then extended with the RESEARCH §Example 2 optional/deferred-classes comment block to meet `must_haves.artifacts[0].min_lines: 20` (final file: 24 lines).

## Issues Encountered
- `python3` in PATH lacks the `mujoco` package; ran validation under `uv run python` to pick up the project venv (mujoco 3.6.0). Not a fix — just the correct runner for this repo.
- Worktree base was not at expected commit `680a3d29…`; reset per `<worktree_branch_check>` protocol before starting Task 1. No work lost (worktree was on a downstream planning commit, not on divergent execution work).

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness
- `data/scenes/scene_office1_gt.yaml` is committed and live-validated; Plan 08 can `open()` it unconditionally at extractor construction.
- Plan 10's coordinator pump has a stable path to reference (`data/scenes/scene_office1_gt.yaml` — matches the `scene_office1_gt\.yaml` must-haves regex).
- No blockers. Mapping will extend additively (add more classes/bodies) without breaking existing consumers.

## Self-Check

- File `data/scenes/scene_office1_gt.yaml` — FOUND
- Commit `2d5578c` — FOUND (`feat(06-07): add scene_office1_gt.yaml COCO->MuJoCo body mapping`)
- Live validation: `python -c "import mujoco,yaml; ..."` → `OK: 2 classes, 7 bodies resolved`
- Frontmatter verification (`chair` in d and `dining_table` in d): OK
- Encoding: utf-8 (acceptance: us-ascii or utf-8 — PASS)
- Line count: 24 (min_lines: 20 — PASS)

## Self-Check: PASSED

---
*Phase: 06-detection-metrics-and-mujoco-gt*
*Completed: 2026-04-15*
