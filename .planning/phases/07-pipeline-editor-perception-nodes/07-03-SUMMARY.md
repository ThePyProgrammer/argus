---
phase: 07
plan: 03
subsystem: tracking
tags: [tracking, registry, protocol, passthrough, scaffolding]
requirements: [DET-PIPELINE-01, DET-PIPELINE-05]
dependency_graph:
  requires:
    - Plan 07-01 (Wave 0 pytest stub for tests/tracking/test_tracker_registry.py)
    - src/perception/types.py::Detections3D + OrientedBox3D (envelope shape)
  provides:
    - TrackerProtocol (runtime-checkable interface)
    - TrackerRegistry (decorator-based backend registry)
    - NoneTracker (passthrough with monotonic counter)
    - src.tracking.trackers side-effect registration entry point
  affects:
    - Plan 07-04/07-05 (frontend tracker_generic node can now enumerate backends)
    - Plan 07-09 (pipeline_builder NodeCatalog will list trackers via TrackerRegistry.list_backends)
    - Plan 07-10 (perception_rgbd preset wires tracker_generic(none))
    - Phase 8 (ByteTrack will slot into TrackerRegistry as tracker_bytetrack)
tech-stack:
  added: []
  patterns:
    - "Mirrored src/slam/registry.py shape (simpler than DetectorRegistry — no D-05/D-06 machinery)"
    - "@tracker decorator + side-effect import (same as @detector_backend / @slam_backend)"
    - "Class-path lazy loading via importlib.import_module in create()"
    - "dataclasses.replace for immutable Detections3D pass-through (geometry byte-identical)"
    - "itertools.count() for session-lifetime monotonic counter (arbitrary-precision int, no overflow)"
key-files:
  created:
    - src/tracking/__init__.py
    - src/tracking/protocol.py
    - src/tracking/registry.py
    - src/tracking/trackers/__init__.py
    - src/tracking/trackers/none.py
  modified:
    - tests/tracking/test_tracker_registry.py (Wave 0 skip-stub → 5 green assertions)
decisions:
  - "Adapted plan test template to real Detections3D shape — plan used placeholder boxes=/robot_id=/tuple geometry; production type uses items=/numpy arrays/image_hw+lifter_ms+n_raw+n_final (Rule 3 blocking fix)"
  - "NoneTracker inherits TrackerProtocol structurally (runtime_checkable duck-typing) — no explicit base class"
  - "tracker() decorator validates CAPABILITIES dict presence but NOT per-key typing (simpler than DetectorRegistry D-06 machinery — trackers have only 3 free-form keys)"
metrics:
  duration: "~7min"
  completed_date: "2026-04-15"
  tasks_completed: 1
  files_created: 5
  files_modified: 1
  tests_passed: "5/5"
---

# Phase 07 Plan 03: tracking-registry-scaffold Summary

## One-liner

Ships `src/tracking/` package with `TrackerProtocol` + `TrackerRegistry` + `NoneTracker` passthrough so Phase 7's `tracker_generic` pipeline-editor node has at least one catalog entry to enumerate, unblocking SC#1 (three-node drag+connect) without waiting for Phase 8's ByteTrack.

## What Shipped

### `src/tracking/` (new package, 5 files)

1. **`__init__.py`** — package marker docstring. Declares Pitfall P9 invariant (module-scope stdlib only) and Phase 7/8 scope split.
2. **`protocol.py::TrackerProtocol`** — `runtime_checkable` Protocol with `track(detections_3d) -> Detections3D` + `reset() -> None` + `CAPABILITIES: dict` attribute. Contract docstring locks Phase 2 D-03 (no geometry mutation) and D-11 (capture_pose / capture_timestamp preservation) invariants.
3. **`registry.py::TrackerRegistry`** — class-path registry mirroring `src/slam/registry.py` shape:
   - `register(name, display, class_path, capabilities, available, install_hint)` — validates `_REQUIRED_CAPABILITIES = ("framework", "produces_stable_ids", "license")` keys are present, raises `ValueError` with sorted missing list.
   - `list_backends()` — returns sorted copy of registry entries (deep-copied capabilities + parameter_schema dicts).
   - `create(name, **kwargs)` — lazy importlib lookup + kwargs passthrough. Raises `ValueError("Unknown tracker: ...")` for unregistered names.
   - `get_default() -> "none"` (per D-13).
   - `_clear()` — test-only reset.
   - `@tracker(name, display, install_hint=None)` decorator — runs `TrackerRegistry.register` at class-definition time.
4. **`trackers/__init__.py`** — one-line side-effect import: `from . import none`. Callers do `import src.tracking.trackers` to populate the registry; no direct module reach.
5. **`trackers/none.py::NoneTracker`** — stateful passthrough. `__init__` creates `self._counter = count(start=0)`; `track(envelope)` builds new `items` via `dataclasses.replace(box, track_id=next(self._counter))` and wraps in `dataclasses.replace(envelope, items=new_items)`. Geometry / capture_pose / capture_timestamp / ms metrics all byte-identical to input. `CAPABILITIES = {"framework": "stub", "produces_stable_ids": False, "license": "MIT"}`. `available()` classmethod returns `(True, None)` — pure-stdlib always loads.

### `tests/tracking/test_tracker_registry.py` (stub → 5 green assertions)

- `test_tracker_registry_lists_none` — registry has "none" with correct display, availability, and full CAPABILITIES triple.
- `test_none_tracker_stamps_monotonic_ids` — 3-box envelope → track_ids `[0, 1, 2]` + geometry byte-identical (numpy array equality).
- `test_none_tracker_preserves_capture_pose_and_timestamp` — Phase 2 D-11 lockdown: capture_pose / capture_timestamp / detector_ms / lifter_ms / n_raw / n_final / image_hw all pass through unchanged.
- `test_tracker_registry_create_unknown_raises` — `ValueError` on unknown name (STRIDE mitigation T-07-05 from threat register).
- `test_tracker_registry_reload_after_clear` — Pitfall 7: `_clear()` → empty list; `importlib.reload(none)` repopulates.

Autouse fixture `_repopulate_registry` wraps each test with `_clear()` → reload-`trackers` → yield → `_clear()` so ordering is deterministic.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Test template used wrong Detections3D construction signature**

- **Found during:** Task 1 implementation, before first test run.
- **Issue:** The plan's test template (lines 411–431) constructed `Detections3D(robot_id=..., boxes=[OrientedBox3D(center=(0.0, 0.0, 0.0), ...)])` with tuple-based geometry. Production `Detections3D` uses `items=...` (not `boxes`), has no `robot_id` field, requires `lifter_ms + detector_ms + n_raw + n_final + image_hw`, and `OrientedBox3D.center / half_extents / quaternion` are `np.ndarray` (shape-checked by `to_wire`), not tuples.
- **Fix:** Rewrote `_make_envelope()` helper to mirror `tests/perception/test_worker_capture_pose.py::items = [OrientedBox3D(center=np.array([float(i), 0.0, 0.0], dtype=np.float64), ...)]` pattern. Also patched `NoneTracker.track()` to iterate `detections_3d.items` (not `.boxes`) and `replace(envelope, items=...)`.
- **Files modified:** `src/tracking/trackers/none.py`, `tests/tracking/test_tracker_registry.py`.
- **Commit:** ead67a8

No Rule 1 bugs or Rule 2 missing-functionality found. No Rule 4 architectural questions triggered.

## Authentication Gates

None — task is pure Python scaffolding with no external services.

## Verification Results

- `pytest tests/tracking/test_tracker_registry.py -x -v` → **5 passed, 0 failed, 0 skipped** (0.03s).
- `python -c "import src.tracking.trackers; from src.tracking.registry import TrackerRegistry; print([b['name'] for b in TrackerRegistry.list_backends()])"` → `['none']`.
- `grep "^import numpy\|^import torch\|^from numpy\|^from torch" src/tracking/ -r` → zero hits (Pitfall P9 module-scope purity invariant upheld).
- `grep "pytest.skip" tests/tracking/test_tracker_registry.py` → zero hits (stub flipped to real assertions).
- Broader regression: `tests/perception/test_protocol_contracts.py` + `test_obb_round_trip.py` → 31 passed (2 pre-existing env-dependent torch failures unchanged). Other perception tests unblocked by my changes but pre-existing skips due to missing `msgpack` / `mujoco` in this environment — out of scope per executor rules.

## Known Stubs

- `NoneTracker.track()` stamps monotonic IDs with no cross-frame association — intentional Phase 7 scaffold (per CONTEXT D-13). Phase 8 (DET-STRETCH-01) replaces with ByteTrack which has `produces_stable_ids: True`. Documented via `CAPABILITIES["produces_stable_ids"] = False` so downstream consumers cannot silently assume stability.
- `PARAMETER_SCHEMA: dict = {}` — NoneTracker exposes no tunables. Frontend tracker ParameterPanel (if ever shown for `tracker_none`) renders empty; ByteTrack ships params alongside in Phase 8.

Both stubs are explicitly planned for Phase 8 resolution; no action required now.

## Threat Model Coverage

From PLAN's `<threat_model>`:

- **T-07-05 (Tampering — `TrackerRegistry.create` arbitrary name):** `mitigate` — covered by `test_tracker_registry_create_unknown_raises` (ValueError on unknown). Downstream REST boundary will convert to HTTP 422 in Plan 07-09.
- **T-07-06 (Elevation — side-effect registration):** `accept` — registration only triggered by in-repo `src.tracking.trackers` import path. No REST/WS reachability.
- **T-07-07 (DoS — counter overflow):** `accept` — `itertools.count()` returns Python arbitrary-precision int; no overflow surface.

No new threat surface introduced beyond plan register.

## Self-Check: PASSED

Verified via direct filesystem + git checks:

- `src/tracking/__init__.py` — FOUND
- `src/tracking/protocol.py` — FOUND (contains `runtime_checkable`)
- `src/tracking/registry.py` — FOUND (contains `class TrackerRegistry` + `def tracker(`)
- `src/tracking/trackers/__init__.py` — FOUND (contains `from . import none`)
- `src/tracking/trackers/none.py` — FOUND (contains `class NoneTracker` + `@tracker(name="none"`)
- `tests/tracking/test_tracker_registry.py` — MODIFIED (no `pytest.skip`, 5 assertions green)
- Commit `ead67a8` — FOUND in `git log --oneline`
