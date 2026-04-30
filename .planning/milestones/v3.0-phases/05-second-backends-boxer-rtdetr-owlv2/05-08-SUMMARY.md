---
phase: 05-second-backends-boxer-rtdetr-owlv2
plan: 08
subsystem: perception
tags: [detector, subprocess, boxer, 3d, obb, licensing]
requirements: [DET-MODELS-03, DET-MODELS-08]
dependency-graph:
  requires:
    - SubprocessDetectorBridge with typed exceptions + wait_for_handshake (Plan 05-05)
    - scripts/boxer_worker.py with FULL-extent msgpack reply schema (Plan 05-06)
    - LICENSES.md with BoxeR CC-BY-NC-4.0 row (Plan 05-02)
    - tests/perception/test_boxer_backend.py + tests/test_licenses_md.py skip-stubs (Plan 05-04)
    - OrientedBox3D + Detections3D dataclasses (Phase 1/2)
    - DetectorRegistry.detector_backend decorator (Phase 1)
  provides:
    - BoxeRBackend composer class (registered as "boxer")
    - BOXER_SHA / BOXER_REPO_URL / BOXER_MODEL_DIR module constants
    - _READY_MARKER / _VENV_DIR / _WORKER_PYTHON / _WORKER_SCRIPT path constants
    - FULL→HALF extent halving translation (D-02 gotcha lockdown)
    - CC-BY-NC-4.0 surface path into Phase 3 DetectorDropdown badge
  affects:
    - src/perception/backends/__init__.py (side-effect import)
    - DetectorRegistry.list_backends() enumeration (now 3 entries: yolov11, rtdetrv2, boxer)
tech-stack:
  added: []
  patterns:
    - "Lazy-spawn composer (D-05): __init__ cheap, warmup() first-call spawns bridge"
    - "FULL→HALF extent translation at composer boundary (D-02)"
    - "Phase 1 D-10 quaternion-invariant: no scipy/Rotation in composer, wire-dict passes through OrientedBox3D() only"
key-files:
  created:
    - src/perception/backends/boxer_backend.py
  modified:
    - src/perception/backends/__init__.py
    - tests/perception/test_boxer_backend.py
    - tests/test_licenses_md.py
    - .planning/phases/05-second-backends-boxer-rtdetr-owlv2/deferred-items.md
decisions:
  - "D-02 extent halving wired explicitly with `float(b3['w']) / 2.0` (etc.) + unit-locked by test_extent_halving"
  - "D-05 lazy-spawn verified by test_construct_no_spawn (patches subprocess.Popen + bridge.start())"
  - "Phase 1 D-10 invariant held: no scipy / Rotation import in composer; test_quaternion_passthrough_no_handcraft grep-locks the source"
  - "Detections3D.image_hw added to composer return (missing from plan snippet; Rule 3 auto-fix — dataclass requires it)"
  - "_COCO_NAMES expanded to full COCO-80 map (plan showed partial dict; full map matches rtdetrv2_backend.py precedent for consistency)"
  - "Docstring/comment phrasing kept free of literal `scipy.` sequence so orchestrator `grep -nE 'from scipy|scipy\\.'` check returns 0 hits"
metrics:
  duration: "~25 min (wall clock)"
  tasks: 2
  files_created: 1
  files_modified: 4
  lines_added: ~445 (composer 281 + tests 164)
  tests_added: 7 active unit tests + 1 slow_boxer integration skip
  tests_passing: "7/7 (boxer) + 4/4 (licenses) + 20/20 (registry) = 31 passing, 1 skipped"
  commits: 3 (RED + GREEN + licenses activation)
completed-date: 2026-04-14
---

# Phase 5 Plan 08: BoxeR Composer Backend Summary

BoxeR CC-BY-NC-4.0 3D-native OBB detector composed as out-of-process backend via SubprocessDetectorBridge, with FULL→HALF extent halving + lazy-spawn + Phase 1 D-10 quaternion invariant preserved in the argus main process.

## Overview

Shipped DET-MODELS-03 (BoxeR subprocess composer) and DET-MODELS-08 (LICENSES.md NC surface). The composer is the 3D-native leg of Phase 5 — it sits in the argus main process, owns a `SubprocessDetectorBridge` instance, and translates msgpack replies from `scripts/boxer_worker.py` into `Detections3D`. The D-02 FULL→HALF extent gotcha is wired explicitly (`float(b3["w"]) / 2.0` etc.) and unit-locked by `test_extent_halving` so the 2×-size render bug cannot silently regress.

## Work Completed

### Task 1: BoxeRBackend composer class (TDD RED + GREEN)

**RED commit `af4ae2c`:** Activated 7 unit tests in `tests/perception/test_boxer_backend.py` replacing the Plan 05-04 skip-stubs. All 7 failed on `ImportError: cannot import name 'boxer_backend' from 'src.perception.backends'`, confirming the failing state before implementation.

**GREEN commit `3f73c3d`:** Created `src/perception/backends/boxer_backend.py` (281 lines) and added the side-effect import to `src/perception/backends/__init__.py`. Key elements:

- `@detector_backend(name="boxer", display="facebook/BoxeR (subprocess)")` — registers in `DetectorRegistry`.
- `CAPABILITIES` dict: `framework="subprocess"`, `license="CC-BY-NC-4.0"` (D-14), `cpu_latency_hint_ms=15000`, `outputs_3d_natively=True` (D-08 LifterDropdown hide), `input_type=DetectorInput.RGBD`, `track_id_support=False`.
- `BOXER_SHA = "df474128a76ba42b05bc81feca7ac1a53fab41af"` — pinned per D-12, mirrors `scripts/boxer_worker.py`.
- `__init__(score_threshold=0.3)` is CHEAP (D-05): stores config, sets `_bridge=None`. No Popen, no socket, no filesystem I/O.
- `_ensure_bridge()` is the lazy-spawn site: checks `_READY_MARKER.exists()`, constructs `SubprocessDetectorBridge(binary_path=subprocess_venvs/boxer/bin/python, args=["scripts/boxer_worker.py"])`, calls `start()` + `wait_for_handshake(timeout_s=60)`.
- `process_frame()` translates the msgpack reply: for each `boxes_3d` entry, halves w/h/d and constructs `OrientedBox3D(...)` with wire-dict qx/qy/qz/qw passed through directly (Phase 1 D-10 invariant — no `scipy.spatial.transform`, no `Rotation.from_matrix`).
- `available()` gates on `subprocess_venvs/boxer/.ready` marker (D-01). Returns `(False, install_hint)` when missing.
- Typed exceptions (`BridgeHangError`, `SubprocessDiedError`) are re-exported via `noqa: F401` so Plan 09's pool handler can import them from the same module.

**Added `image_hw` to the `Detections3D` envelope** (Rule 3 auto-fix): the plan's snippet omitted the field, but the `Detections3D` dataclass requires it. Composer passes `(H, W) = frame.rgb.shape[:2]`.

### Task 2: Activate tests/test_licenses_md.py (commit `1f8fda2`)

Replaced 4 Plan 05-04 skip-stubs with real assertions:
- `test_licenses_md_exists` — file present at repo root.
- `test_boxer_cc_by_nc_present` — content contains `CC-BY-NC-4.0` + `facebook/BoxeR`.
- `test_agpl_apache_mit_entries_present` — SPDX tags AGPL-3.0, Apache-2.0, MIT all present.
- `test_nc_compliance_section_present` — `## NC Compliance Mechanism` section anchor present.

All 4 pass against the LICENSES.md that Plan 05-02 shipped — no LICENSES.md content changes needed.

## Decisions Made

- **Detections3D.image_hw included** — plan snippet missing it, but dataclass requires it. Added `image_hw=(int(H), int(W))` at `process_frame` return.
- **Full COCO-80 `_COCO_NAMES` dict** — plan showed partial dict (15 entries); expanded to 80 entries mirroring `rtdetrv2_backend.py` so uncommon BoxeR outputs get proper class_name instead of `class_{id}` fallback.
- **Docstring avoids literal `scipy.`** — one `scipy.spatial.transform` reference in docstring/comment was rephrased to "no Rotation import" so the orchestrator's `grep -nE "from scipy|scipy\\."` check returns 0 hits as required. The assertion in `test_quaternion_passthrough_no_handcraft` uses stricter literals (`"from scipy.spatial.transform"`, `"Rotation.from_matrix"`) that were never present.

## Deviations from Plan

**None intentional.** Two minor additions treated as Rule 3 (blocking issue) auto-fixes:

1. **`Detections3D.image_hw` field added to `process_frame` return** — the plan's code snippet omitted `image_hw` but the `Detections3D` dataclass declares it as a required field. Returning the dataclass without `image_hw` would `TypeError` at runtime. Added `image_hw=(int(H), int(W))` using the numpy shape of `frame.rgb`. No impact on plan grep acceptance criteria.

2. **Rephrased `scipy.spatial.transform` references in composer docstrings/comments** — two explanatory comments mentioned `scipy.spatial.transform` by literal name. The orchestrator's phase-level invariant check `grep -nE "from scipy|scipy\." src/perception/backends/boxer_backend.py returns 0 hits` would flag these false positives. Rephrased to "no Rotation import" which is semantically identical. The stricter grep test (`from scipy.spatial.transform` literal) was never at risk — that full import statement was never in the source.

## Known Stubs

None. All BoxeR data flows from a real subprocess worker (Plan 06) through the bridge (Plan 05) into real `OrientedBox3D` dataclass instances. The `test_warmup_returns_3d` integration test stays `@pytest.mark.slow_boxer` and skips by default — but this is an execution-environment gate (requires real `subprocess_venvs/boxer/.ready`), not a stubbed data path.

## Verification Results

```
$ uv run pytest tests/perception/test_boxer_backend.py tests/test_licenses_md.py tests/perception/test_registry.py -x --timeout=60
================== 31 passed, 1 skipped, 3 warnings in 0.09s ===================

$ uv run python -c "import src.perception.backends; from src.perception.registry import DetectorRegistry; e = [x for x in DetectorRegistry.list_backends() if x['name']=='boxer'][0]; print(e['capabilities']['license'], e['capabilities']['outputs_3d_natively'], e['available'])"
CC-BY-NC-4.0 True False
# Matches plan's expected verification output exactly.
```

**Plan grep acceptance criteria — all pass:**

| Check | Expected | Actual |
|-------|----------|--------|
| `class BoxeRBackend:` | 1 | 1 |
| `BOXER_SHA: str = "df474128..."` | 1 | 1 |
| `"license": "CC-BY-NC-4.0"` | 1 | 1 |
| `"outputs_3d_natively": True` | 1 | 1 |
| `@detector_backend(name="boxer"` | 1 | 1 |
| `from scipy.spatial.transform` | 0 | 0 |
| `grep -nE "from scipy|scipy\."` | 0 hits | 0 hits |
| `float(b3["w"]) / 2.0` | 1 | 1 |
| `OrientedBox3D(` | ≥1 | 2 |
| `wait_for_handshake` | 1 | 1 |
| `subprocess.Popen / Popen(` | 0 | 0 |
| `from . import boxer_backend` in `__init__.py` | 1 | 1 |

**Phase-wide `uv run pytest tests/ -m "not slow_boxer and not network"` does NOT exit 0**, but every failure is pre-existing environmental (missing `fastapi` / `onnxruntime` extras on default `uv sync`) or a known test-ordering flake — all documented in `deferred-items.md`. Plan 05-08's narrow verification block passes clean.

## Deferred Issues

Appended a new entry to `deferred-items.md`:
- **Plan 05-08: `onnxruntime` missing in default dev env blocks most rtdetrv2 tests** — 4 tests in `tests/perception/test_rtdetrv2_backend.py` fail at `import onnxruntime` because `perception` extra isn't auto-installed by default `uv sync`. Pre-existing (present on base commit `19b1c2c`). Same root cause as the 05-05 fastapi/torch item. Fix is a dev-env / CI ergonomics concern (document `uv sync --extra perception`), not a plan-level scope item.

## Threat Flags

No new threat surface introduced beyond what the plan's `<threat_model>` covers. T-5-02 (msgpack reply tampering) is mitigated by: composer only reads specific string keys (`tx`, `ty`, `tz`, `qx`, `qy`, `qz`, `qw`, `w`, `h`, `d`, `classes`, `scores`, `bboxes`) with `float()`/`int()` coercion; unknown keys are ignored via `.get()`. T-5-03 (SHA pinning) is mitigated by the module-level `BOXER_SHA` constant mirrored across `boxer_worker.py` + `setup_boxer_subprocess.sh` + `download_models.py`. T-5-06 (path injection) mitigated: all paths built from module-level `Path(...)` constants, no user input flows into `_VENV_DIR` / `_READY_MARKER` / `_WORKER_PYTHON` / `_WORKER_SCRIPT`.

## Self-Check: PASSED

- `src/perception/backends/boxer_backend.py` — FOUND
- `tests/perception/test_boxer_backend.py` — FOUND (7 active tests + 1 slow_boxer skip)
- `tests/test_licenses_md.py` — FOUND (4 active tests)
- Commit `af4ae2c` (RED) — FOUND
- Commit `3f73c3d` (GREEN) — FOUND
- Commit `1f8fda2` (licenses) — FOUND
- `src/perception/backends/__init__.py` contains `from . import boxer_backend` — VERIFIED
- All plan success criteria satisfied.
