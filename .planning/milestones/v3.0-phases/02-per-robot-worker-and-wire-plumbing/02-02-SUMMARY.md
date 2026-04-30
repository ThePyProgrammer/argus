---
phase: 02-per-robot-worker-and-wire-plumbing
plan: 02
subsystem: testing
tags: [perception, invariant, grep, ci-guard, d-10, wire-format]

# Dependency graph
requires:
  - phase: 02-per-robot-worker-and-wire-plumbing
    provides: "OrientedBox3D.to_wire canonical serializer (Plan 02-01) — the single legal source of the \"quaternion\": literal."
provides:
  - "D-10 grep invariant CI guard (tests/perception/test_no_inline_quaternion.py) — any backend/emitter that constructs inline quaternion dict literals fails the test with file:line hits."
affects: [02-04-streaming-viz-emitter, 05-boxer-rt-detr-backend, all-future-detector-backends]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "CI-enforced grep invariants as architectural guards — pattern applicable to any D-level contract that must not leak across module boundaries."

key-files:
  created:
    - tests/perception/test_no_inline_quaternion.py
  modified: []

key-decisions:
  - "Use plain system `grep` via subprocess (not ripgrep) so the test runs on any dev machine without extra deps."
  - "Whitelist by path substring `types.py` rather than by exact path — keeps the test resilient to future repackaging of OrientedBox3D as long as it lives in a file named types.py."
  - "Cap reported offenders at 5 so the assertion message stays scannable; the count and full exit status still communicate the scale of the violation."

patterns-established:
  - "Invariant guard test pattern: subprocess.run grep → split into allowed/disallowed buckets by path predicate → two asserts (zero disallowed + expected allowed count) → human-readable file:line offender list."

requirements-completed: [DET-3D-03]

# Metrics
duration: 3 min
completed: 2026-04-14
---

# Phase 02 Plan 02: D-10 Inline Quaternion Invariant Summary

**CI-enforced grep guard ensuring only `OrientedBox3D.to_wire` in `src/perception/types.py` constructs the literal `"quaternion":` — future backends must call `to_wire()` or fail the test.**

## Performance

- **Duration:** ~3 min
- **Tasks:** 1
- **Files created:** 1
- **Files modified:** 0

## Accomplishments
- D-10 architectural invariant is now mechanically enforced — no human reviewer needed to spot inline quaternion dict literals in backends or emitters.
- Test runs in ~0.02 s (well under the 1 s Nyquist sampling budget for quick-run suites).
- Offender output cites exact `file:line:matched-line` via `grep -n`, capped at 5 to keep failures scannable.
- Artificial-offender spot check confirmed the guard fires cleanly: adding `x = {"quaternion": [0,0,0,1]}` in any non-`types.py` file under `src/` produces an actionable assertion.

## Task Commits

1. **Task 1: D-10 grep invariant test** — `dab65cc` (test)

**Plan metadata:** (this commit)

## Files Created/Modified
- `tests/perception/test_no_inline_quaternion.py` — 35-line guard with a single test `test_no_inline_quaternion_literal`. Shells out to system `grep -rn '"quaternion":' src/`, filters hits by whether the path contains `types.py`, asserts zero disallowed hits and exactly one allowed hit.

## D-10 Invariant Rationale

The wire contract for a 3D oriented bounding box includes a `quaternion` field with a fixed qw-sign convention (xyzw order, `qw >= 0` canonicalization) and exact field ordering. Plan 02-01 established `OrientedBox3D.to_wire` as the single legal serializer honoring that contract.

Without this guard, a Phase 5 BoxeR or RT-DETR backend — or a future emitter — could trivially build the wire payload via `{"quaternion": [...], ...}` inline and diverge silently on:

- **Sign convention** (qw negative branch)
- **Field order** (if downstream consumers rely on JSON object iteration order)
- **Number coercion** (e.g., emitting `np.float32` instead of `float`)

Code review catches this unreliably. A grep-based CI test catches it deterministically: the literal string `"quaternion":` simply cannot appear anywhere in `src/` outside `types.py`, and the test tells the offender exactly where they introduced it.

## Test Mechanics

Two-bucket filter on grep output:

1. Run `grep -rn '"quaternion":' src/` via `subprocess.run` (capture stdout as text).
2. `allowed = [h for h in hits if "types.py" in h]` — hits inside any `types.py`.
3. `disallowed = [h for h in hits if "types.py" not in h]` — everything else.
4. `assert not disallowed` → fails with first 5 offenders printed.
5. `assert len(allowed) == 1` → catches the opposite failure mode where someone accidentally removes the canonical serializer or duplicates it inside `types.py`.

`REPO` is computed as `pathlib.Path(__file__).resolve().parents[2]` from `tests/perception/test_no_inline_quaternion.py`, which resolves to the project root regardless of where pytest is invoked from.

No ripgrep dependency — plain `grep` is available on every dev machine and CI runner.

## Note to Wave 4 (Plan 02-04 — streaming viz emitter)

When Plan 02-04 builds the streaming viz emitter, it **MUST** call `Detections3D.to_wire()` (or `OrientedBox3D.to_wire()` per-box) rather than constructing the wire envelope inline. A line like:

```python
# DO NOT DO THIS in src/perception/streaming_viz.py or anywhere else in src/
payload = {"box": {"quaternion": [qx, qy, qz, qw], ...}}
```

…will fail `pytest tests/perception/test_no_inline_quaternion.py` immediately and block the plan's commit verification. Use the canonical serializer.

The same applies to every future detector backend (Phase 5 BoxeR/RT-DETR and beyond) and to any subprocess-bridge helper that marshals detections across the process boundary.

## Decisions Made
- **Plain `grep` (system tool) over ripgrep.** Zero new deps; present on every dev box and CI image; output format is identical enough (`file:line:match`) that `in` substring matching is bulletproof.
- **Path whitelist via `"types.py" in h`** rather than hard-coding `src/perception/types.py`. Keeps the guard stable if OrientedBox3D is later relocated (e.g., into `src/perception/wire/types.py`) as long as the file name stays `types.py`. Acceptable because no other file in `src/` is named `types.py`.
- **Cap offender report at 5** so a big refactor that accidentally introduces the literal in many places still produces a scannable failure message; the total count is also printed.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Verification Evidence

- `pytest tests/perception/test_no_inline_quaternion.py -x -q` → `1 passed` in 0.02 s.
- `grep -rn '"quaternion":' src/` → exactly one hit: `src/perception/types.py:135`, inside `OrientedBox3D.to_wire`.
- **Artificial offender spot-check:** Temporarily created `src/perception/_offender.py` containing `x = {"quaternion": [0, 0, 0, 1]}`. The test failed with:
  ```
  E  assert not ['.../src/perception/_offender.py:2:x = {"quaternion": [0, 0, 0, 1]}']
  ```
  Offender file was removed; test returned to green.

## Next Plan Readiness

- Wave 2 parallel siblings (02-03, 02-07) are independent — no file overlap with this plan.
- When Plan 02-04 lands (streaming viz emitter), this guard will enforce that it uses the canonical serializer. Planner/executor for 02-04 should include this test in their quick-suite run.
- Phase 5 detector backend plans inherit this invariant automatically; no additional setup needed.

---
*Phase: 02-per-robot-worker-and-wire-plumbing*
*Completed: 2026-04-14*

## Self-Check: PASSED
- File created: `tests/perception/test_no_inline_quaternion.py` (verified via `[ -f ]`).
- Commit `dab65cc` present on branch: `test(02-02): add D-10 grep invariant for inline quaternion literals`.
- Test green (`1 passed` in 0.02 s).
- Precondition verified: `grep -rn '"quaternion":' src/` returns exactly one hit, inside `src/perception/types.py`.
- Artificial offender check: test correctly fails with file:line when a violator is introduced.
