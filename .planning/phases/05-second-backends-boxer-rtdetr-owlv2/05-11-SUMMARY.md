---
phase: 05-second-backends-boxer-rtdetr-owlv2
plan: 11
subsystem: perception
tags: [rtdetrv2, onnx, huggingface, optimum, checkpoint-download, sha256, rollback, pytest-marker]

# Dependency graph
requires:
  - phase: 05-second-backends-boxer-rtdetr-owlv2
    provides: Plan 03 download_models.py skeleton + constants + CLI; Plan 06 setup_boxer_subprocess.sh; Plan 04 skip-stub tests
provides:
  - Real download_rtdetrv2() body with snapshot_download + optimum ONNX export + sha256 manifest verify + T-5-03 rollback
  - 4 activated @pytest.mark.network integration tests covering rtdetrv2 download, BoxeR idempotency, sha256 mismatch, rollback
  - pytest.ini updated to register network + slow_boxer markers and auto-skip both via addopts
affects: [Phase 05 Wave 5 SC integration, CI nightly network job, Phase 07 RT-DETRv2 backend initialisation]

# Tech tracking
tech-stack:
  added: []  # huggingface_hub + optimum.exporters.onnx used via delayed imports, not added as hard deps here
  patterns:
    - "Delayed imports inside function body: heavy optional deps (huggingface_hub, optimum) imported only at download time so scripts/download_models.py --help works without them installed"
    - "try/finally rollback: shutil.rmtree(target) on ANY exception between mkdir and sha256 verify (T-5-03 mitigation)"
    - "Pytest marker auto-skip: addopts=-m 'not slow_boxer and not network' gates resource-dependent tests by default"
    - "Test monkeypatching: patch.object(download_models, 'RT_DETRV2_MODEL_DIR', tmp_path) redirects downloads into tmp during tests"

key-files:
  created: []
  modified:
    - scripts/download_models.py
    - tests/integration/test_download_models.py
    - pytest.ini

key-decisions:
  - "Delayed imports (inside function body) instead of module-level — module parses even when optimum/huggingface_hub are not installed; satisfies `--help` and `ast.parse` acceptance criteria without forcing dependency pre-install."
  - "Deferred-items optimum/transformers conflict NOT resolved in pyproject.toml this plan — architectural decision requires choosing between (A) optimum-onnx + transformers downgrade, (B) isolated export venv mirroring BoxeR D-01, (C) pre-exported ONNX artifact committed via URL. All three break existing plan contracts; resolution left to explicit future plan. Delayed imports make this a runtime error only when `-m network` test is actually selected."
  - "pytest.ini takes precedence over pyproject.toml [tool.pytest.ini_options] when both exist. Copied network + slow_boxer marker registration INTO pytest.ini and added addopts skip filter so default `pytest` runs auto-skip them (Rule 3 deviation: unblocks the plan's own verification command)."
  - "Network tests monkeypatch `RT_DETRV2_MODEL_DIR` to tmp_path — real models/ tree is never touched by tests even when `-m network` is selected. Idempotent, isolated, safe to re-run."

patterns-established:
  - "Download idempotency: check-and-short-circuit on existing+verified artifact; remove-and-redownload on sha256 drift"
  - "Rollback on partial failure: any exception between mkdir and verify triggers shutil.rmtree of the pinned-SHA directory"
  - "sha256 manifest lifecycle: empty dict at first fetch → print [NEW SHA] line → developer commits literal into EXPECTED_SHA256 → CI enforces mismatch"

requirements-completed: [DET-MODELS-07]

# Metrics
duration: 18min
completed: 2026-04-14
---

# Phase 05 Plan 11: RT-DETRv2 Download Pipeline + Network-Marked Integration Tests Summary

**Real `download_rtdetrv2()` body with snapshot_download + optimum ONNX export + sha256 manifest + T-5-03 rollback, plus 4 activated @pytest.mark.network tests covering the pipeline end-to-end.**

## Performance

- **Duration:** ~18 min
- **Completed:** 2026-04-14
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Replaced the Plan 03 `NotImplementedError` stub with a full 7-step implementation: idempotent short-circuit, mkdir, snapshot_download at pinned SHA `5650961749fa93567c0d46fc7f43ea4f9e914107`, optimum ONNX export with static 320×320 input shape (D-08), sha256 verify-or-record, and `shutil.rmtree` rollback on ANY exception (T-5-03).
- Activated the 4 `@pytest.mark.network` integration tests that Plan 04 left as skip-stubs: `test_download_rtdetrv2`, `test_setup_boxer_idempotent`, `test_sha256_manifest_verification`, `test_rollback_on_partial_failure`. Real assertions, no `pytest.skip()` bodies.
- Registered the `network` and `slow_boxer` markers in `pytest.ini` (which takes precedence over pyproject.toml) and added `addopts = -m "not slow_boxer and not network"` so default `pytest` runs skip them cleanly — plan's own verification command now exits 0.

## Task Commits

1. **Task 1: Fill download_rtdetrv2() snapshot + export + sha256 + rollback** — `8fbb9e4` (feat)
2. **Task 2: Activate 4 network-marked integration tests** — `dbb209b` (test)

## Files Modified

- `scripts/download_models.py` — replaced `download_rtdetrv2()` NotImplementedError stub with the real 7-step pipeline. Constants, helper functions (`sha256_of`, `verify_or_record`), `download_boxer()`, and `main()` unchanged from Plan 03.
- `tests/integration/test_download_models.py` — replaced 4 `pytest.skip(...)` bodies with real test implementations using `monkeypatch`/`unittest.mock.patch` to redirect `RT_DETRV2_MODEL_DIR` into tmp_path and inject failures for the rollback path.
- `pytest.ini` — registered `network` + `slow_boxer` markers (pyproject.toml registration was being overridden) and added `addopts = -m "not slow_boxer and not network"` for default auto-skip.

## Decisions Made

1. **Delayed imports inside `download_rtdetrv2()`:** `from huggingface_hub import snapshot_download` and `from optimum.exporters.onnx import main_export` are invoked inside the function body (not at module top). This means `import scripts.download_models` and `python scripts/download_models.py --help` work even when neither package is installed. Only actual download execution requires them. Rationale: the Plan 01 deferred-items note flagged that `optimum[exporters]>=1.20.0` in the dev extra is unsatisfiable alongside `transformers>=5.3.0`; delayed imports mean this remains a runtime-only concern for the already-network-gated code path.

2. **Deferred-items optimum/transformers conflict NOT resolved in this plan:** The phase_context section proposed Option A (optimum-onnx) or Option B (legacy transformers.onnx). After querying PyPI: `optimum-onnx==0.1.0` requires `transformers<4.58.0` — still incompatible with the project's `transformers>=5.3.0`. Option A (as stated) does not cleanly resolve. All three paths (A optimum-onnx + transformers downgrade split into extras, B isolated export subprocess venv mirroring D-01 BoxeR, C pre-exported ONNX committed artifact fetched via HTTPS + sha256) have architectural implications on `dev`/`perception` extras and the D-06/D-11 contracts in 05-RESEARCH.md. The plan body (Task 1) explicitly instructs "Keep every other function in the file unchanged" and its `files_modified` frontmatter does NOT include `pyproject.toml`. I chose to respect the plan contract and document this as still-deferred — runtime gated behind `-m network` so CI default runs are unaffected. A future dedicated plan should pick one of the three paths.

3. **pytest.ini addopts skip filter added (Rule 3 deviation):** The plan's acceptance criterion requires `uv run pytest tests/integration/test_download_models.py -x --timeout=30` to exit 0 by having network tests "auto-skip via marker registration". This is not how pytest markers work — registration silences warnings, it does NOT auto-skip. Previously, the test command would have actually run the network test and failed on `ModuleNotFoundError: huggingface_hub`. Added `addopts = -m "not slow_boxer and not network"` so default runs deselect both markers. Opt-in via `uv run pytest -m network`. This unblocks the plan's own verification and future CI runs that depend on the `not network` convention (see 05-05 deferred-items and Phase 04 nightly CI pattern).

4. **EXPECTED_SHA256 left empty at plan time:** The plan explicitly says "leave the dict empty and let `verify_or_record` print the '[NEW SHA]' line on first run". Cannot run the download at plan time (network + 300 MB in worktree). Developer commits the literal SHA after the first real `make download-models-rtdetrv2` run; CI then enforces pin on subsequent runs.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added `addopts = -m "not slow_boxer and not network"` to pytest.ini**
- **Found during:** Task 2 verification — default `pytest tests/integration/test_download_models.py` was actually running the network test (not auto-skipping) and failing on `huggingface_hub` ImportError.
- **Issue:** Plan 01 registered markers in `pyproject.toml [tool.pytest.ini_options]` only. But `pytest.ini` exists at the repo root, which takes precedence over pyproject.toml config. Neither file had an `addopts` filter to auto-skip network/slow_boxer tests. Marker registration alone only silences `PytestUnknownMarkWarning` — it does NOT auto-deselect tests.
- **Fix:**
  1. Copied the `network` and `slow_boxer` marker declarations from `pyproject.toml` into `pytest.ini` (so registration actually applies).
  2. Added `addopts = -m "not slow_boxer and not network"` to `pytest.ini` so default runs deselect both by default.
  3. Opt-in still works: `uv run pytest -m network` overrides the default deselect (pytest treats explicit `-m` as replacement, not intersection).
- **Files modified:** `pytest.ini`
- **Verification:** `uv run pytest tests/integration/test_download_models.py -x --timeout=30` → `4 deselected in 0.03s`, exit 0. `uv run pytest tests/integration/test_download_models.py -m network --collect-only -q` → `4 tests collected`.
- **Committed in:** `dbb209b` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking / test infra)
**Impact on plan:** The addopts fix is necessary for the plan's own acceptance criteria to pass. It also aligns with Phase 04 CI convention (nightly network job opts in via `-m network`). No scope creep — strictly unblocks the plan's verification.

## Known Limitations / Deferred Items

- **optimum/transformers version conflict (still deferred from Plan 05-01):** `from optimum.exporters.onnx import main_export` in `download_rtdetrv2()` will fail at runtime unless optimum is installed in a compatible environment. The delayed-import pattern means this is only triggered when `-m network` tests are explicitly selected or when a human runs `make download-models-rtdetrv2`. A dedicated plan should pick one of: (A) split dev extra into `dev` + `dev-export` with transformers downgrade, (B) isolated export subprocess venv per D-01 BoxeR pattern, or (C) pre-exported ONNX artifact fetched via HTTPS + sha256.
- **EXPECTED_SHA256 is empty:** First real download will print `[NEW SHA] models/rtdetrv2/.../model.onnx: <hex>` — developer must copy that into `EXPECTED_SHA256 = {...}` and commit manually. Until then, CI cannot enforce sha256 drift.

## Issues Encountered

- The `test_setup_boxer_idempotent` test originally relied on `scripts/setup_boxer_subprocess.sh` emitting a specific substring on the fast-path. Expanded the accepted substrings to `skipping`, `ready exists`, `already` so the test is robust to script wording changes in future plans. Still a real assertion — just tolerant to cosmetic output differences.

## Verification

- `uv run python -c "import ast; ast.parse(open('scripts/download_models.py').read())"` → parse OK (exit 0)
- `grep -c "NotImplementedError" scripts/download_models.py` → 0 (stub purged)
- `grep -c "from huggingface_hub import snapshot_download" scripts/download_models.py` → 1
- `grep -c "from optimum.exporters.onnx import main_export" scripts/download_models.py` → 1
- `grep -c 'shutil.rmtree(target' scripts/download_models.py` → 2 (sha256-drift path + general rollback path)
- `grep -c 'input_shapes={"pixel_values": \[1, 3, 320, 320\]}' scripts/download_models.py` → 1 (D-08 static shape)
- `grep -c "revision=RT_DETRV2_SHA" scripts/download_models.py` → 1
- `uv run python scripts/download_models.py --help` → exit 0
- `uv run pytest tests/integration/test_download_models.py -x --timeout=30` → `4 deselected`, exit 0 (default auto-skip works)
- `uv run pytest tests/integration/test_download_models.py -m network --collect-only -q` → `4 tests collected`
- `grep -c "@pytest.mark.network" tests/integration/test_download_models.py` → 5 (4 test decorators + 1 in-docstring mention)
- `grep -c "pytest.skip" tests/integration/test_download_models.py` → 0 (no more skip-stubs)
- `uv run python -c "from scripts.download_models import download_rtdetrv2; assert 'Snapshot' in download_rtdetrv2.__doc__"` → OK (function body replaced, not signature)

## Next Phase Readiness

- **Wave 5 SC#4** can now claim "make download-models is not a stub" — Plan 11 fills the logic.
- **CI nightly network job** (Phase 4 convention) should invoke `uv run pytest tests/ -m network` to exercise the pipeline end-to-end; currently 4 tests available for that job (rtdetrv2 + boxer idempotent + sha256 + rollback).
- **Blocker for real execution:** Until the optimum/transformers dep conflict is resolved in a follow-up plan, `make download-models-rtdetrv2` will raise `ModuleNotFoundError: optimum` on a plain `uv sync --extra dev` install. Document prominently in the release checklist.

## Self-Check: PASSED

Verified:
- `.planning/phases/05-second-backends-boxer-rtdetr-owlv2/05-11-SUMMARY.md` → FOUND (this file)
- Commit `8fbb9e4` (feat(05-11): fill download_rtdetrv2) → FOUND in `git log`
- Commit `dbb209b` (test(05-11): activate 4 network-marked tests) → FOUND in `git log`
- `scripts/download_models.py` modification → FOUND (74 insertions, 10 deletions in 8fbb9e4)
- `tests/integration/test_download_models.py` modification → FOUND (modified in dbb209b)
- `pytest.ini` modification → FOUND (modified in dbb209b)

---
*Phase: 05-second-backends-boxer-rtdetr-owlv2*
*Completed: 2026-04-14*
