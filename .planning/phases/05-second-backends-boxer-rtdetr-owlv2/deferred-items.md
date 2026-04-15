# Phase 5 Deferred Items

Items discovered during execution that are out of scope for the current plan but must be addressed later.

---

## Plan 05-01: optimum / transformers version conflict (for Plan 05-04 to resolve)

**Discovered:** 2026-04-15 during 05-01 execution while running `uv lock --check`.

**Issue:** The Wave 0 scaffolding plan literal `"optimum[exporters]>=1.20.0"` (D-06) is silently broken at the working-set level when combined with the existing `perception` extra pin `"transformers>=5.3.0"`:

- **optimum 1.x** (the only line that exposes the `[exporters]` extra) caps `transformers<4.54.0`. Co-installing `argus[dev]` and `argus[perception]` is unsatisfiable: `uv lock --check --resolution=highest` with `<2.0` upper bound on optimum produces "your project's requirements are unsatisfiable" (transformers 5.3 vs <4.54).
- **optimum 2.x** (currently 2.1.0) DROPPED the `exporters` extra. `uv lock` resolves to `optimum==2.1.0` and emits `warning: The package optimum==2.1.0 does not have an extra named "exporters"`. The `optimum.exporters.onnx.main_export` symbol that RESEARCH § D-06 documents is NOT importable from optimum 2.x alone — it was extracted to a separate `optimum-onnx` package.
- **`optimum-onnx`** package (the new home of `main_export` for optimum 2.x) requires `transformers<4.58`, also incompatible with the project's `transformers>=5.3.0` pin.

**Impact:** Plan 05-04 (`scripts/download_models.py`) will fail at `from optimum.exporters.onnx import main_export` when run from a `argus[dev]` install, regardless of whether the user pre-installed `argus[perception]`.

**Why deferred to Plan 05-04, not auto-fixed in 05-01:**
- Resolution requires architectural choice (downgrade transformers pin? switch to optimum-onnx + override transformers? use a separate isolated dev venv for the export step? export RT-DETRv2 ONNX out-of-band one-time and commit the artifact?).
- Plan 05-01 is pure scaffolding — its job is to land the dep token the planner specified, not to redesign the export pipeline.
- The plan author explicitly chose `optimum[exporters]>=1.20.0` as the literal token — Wave 0 acceptance criteria match it byte-for-byte. Changing the token here would break grep-based verification.
- Pre-existing `uv lock` had this exact dep token resolving with the same warning; the warning is not new noise introduced by 05-01.

**Required action in Plan 05-04 (RT-DETRv2 download script):**
1. Pick one resolution path:
   - **(A)** Bump `optimum[exporters]` constraint up; switch `dev` extra to `optimum-onnx>=0.1.0` and accept that the `dev` install profile must downgrade `transformers` (split `dev` into `dev` + `dev-export` extras or use `tool.uv.environments` markers).
   - **(B)** Run the ONNX export inside an isolated subprocess venv (mirrors D-01 BoxeR pattern): create `subprocess_venvs/rtdetrv2_export/` with its own `transformers<4.54` + `optimum[exporters]==1.27.0`, invoke `optimum-cli export onnx ...` from there. Main venv stays clean.
   - **(C)** Pre-export RT-DETRv2 ONNX once (in any environment), publish to a sha256-pinned URL, fetch in `download_models.py` via plain HTTPS — drop optimum from the dep tree entirely.
2. Update `pyproject.toml` accordingly. Update `D-06` notes in 05-RESEARCH.md if the strategy changes from "optimum.exporters.onnx.main_export at runtime."
3. Confirm `uv lock --check` resolves clean (no warnings on missing extras).

**Verification command for 05-04:**
```bash
uv lock 2>&1 | grep -i "warning\|error" | grep -v "yanked"  # must be empty
uv run python -c "from optimum.exporters.onnx import main_export; print('OK')"  # must succeed
```

---

## Plan 05-05: Pre-existing `fastapi` / `torch` import errors outside scope

**Discovered:** 2026-04-15 during 05-05 execution while running the phase-wide
`uv run pytest tests/ -m "not slow_boxer and not network"` regression command
from the plan's `<verification>` block.

**Issue:** Several test modules fail at collection or run time with
``ModuleNotFoundError: No module named 'fastapi'`` (or `'torch'`) on a default
``uv sync`` — the ``perception`` + ``web`` optional extras are not
auto-installed by `uv sync` without `--all-extras`. Affected files (not caused
by Plan 05-05):

- `tests/mcp/test_mcp_server.py`
- `tests/perception/test_detector_routes.py`
- `tests/perception/test_lifter_routes.py`
- `tests/perception/test_lifter_hotswap.py` (fastapi)
- `tests/web/test_*` (all five)
- `tests/perception/test_protocol_contracts.py::test_torch_backend_mixin_*` (torch)
- `tests/perception/test_point_cluster_lifter.py::test_open3d_extent_divided_by_two` (open3d)
- `tests/slam/test_openvins_backend.py::TestOpenVINSRegistration::test_registered_as_openvins` (missing openvins stub on plain install)
- `tests/integration/test_multi_mode.py` + `tests/integration/test_multi_robot_integration.py` (ValueError on coordinator construction — pre-existing, unrelated to detector bridge)

**Scope decision:** Not auto-fixed per the executor's SCOPE BOUNDARY rule — these
failures exist on the pre-05-05 base (commit ``10202b7``) and are caused by
development-install profile mismatches, not by the bridge changes in 05-05.
The narrow verification command the plan specifies
(`uv run pytest tests/perception/test_subprocess_bridge*.py tests/perception/test_crash_fallback.py tests/perception/test_registry.py tests/perception/test_thread_config.py --timeout=30`)
passes cleanly. Phase-level CI configuration for auto-installing `[perception,web]`
extras is a Phase 6+ concern.

**Required action (future / environment hygiene):**
1. Document `uv sync --extra perception --extra web --extra dev` in CONTRIBUTING
   or a `Makefile` target so contributors get a working test bed.
2. Consider splitting the top-level `tests/` into extra-gated subpackages with
   `pytest_plugins`-based skips when the extra is absent.

---

## Plan 05-07: `tests/perception/test_point_cluster_lifter.py::test_point_cluster_lifter_registered` test-ordering flake

**Discovered:** 2026-04-15 during 05-07 execution while running the plan's
`<verification>` block `uv run pytest tests/ -x --timeout=120 -m "not slow_boxer and not network"`.

**Issue:** `test_point_cluster_lifter_registered` fails when run in the full
`tests/perception/` sweep but passes in isolation:

```
uv run pytest tests/perception/test_point_cluster_lifter.py::test_point_cluster_lifter_registered  # PASSES
uv run pytest tests/perception/ -x                                                                   # FAILS this test
```

**Scope decision:** Not auto-fixed per the executor's SCOPE BOUNDARY rule —
verified present on the pre-05-07 base (`2854c68`) using
`git checkout 2854c68 -- . && uv run pytest tests/perception/`. The failure
predates RT-DETRv2 backend work and is unrelated to the 05-07 artifacts
(rtdetrv2_backend.py, test_rtdetrv2_backend.py, fixtures/*.npz). Root cause
appears to be a test-ordering side effect where another test module leaves
`Detection3DRegistry` in a state that fails the `point_cluster_lifter`
registration assertion — likely `registry._clear()` called by a fixture that
doesn't re-register lifters. Fix belongs in a test-infra cleanup plan
(conftest autouse registry-restore fixture), not in a backend-landing plan.

**Required action (future):**
1. Add an autouse fixture in `tests/perception/conftest.py` that snapshots
   `DetectorRegistry._backends` + `Detection3DRegistry._backends` dicts before
   each test and restores them after, OR re-runs the side-effect-import at
   session start.
2. Consider making registry `_clear()` reset to a baseline snapshot instead of
   empty dict.

---

## Plan 05-08: `onnxruntime` missing in default dev env blocks most rtdetrv2 tests

**Discovered:** 2026-04-15 during 05-08 execution while running the phase-wide
`uv run pytest tests/ -m "not slow_boxer and not network"` regression command.

**Issue:** On a default `uv sync` install, `onnxruntime` is not present
(it lives in the `perception` extra). Running
`uv run pytest tests/perception/test_rtdetrv2_backend.py` fails 4 tests at the
`_install_fake_session` helper that tries `import onnxruntime as ort`. Affected
tests (not caused by Plan 05-08):

- `test_construct_no_onnx_file_raises`
- `test_construct_with_onnx_file_succeeds`
- `test_warmup_runs_one_inference`
- `test_thread_budget_inherits_from_thread_config`

**Scope decision:** Not auto-fixed per executor's SCOPE BOUNDARY rule. The
failures are pre-existing (pre-05-08 base commit `19b1c2c`) and caused by the
default-install profile not pulling the `perception` extra — same root cause as
the `fastapi`/`torch` items above. Plan 05-08 adds zero new lines to
`test_rtdetrv2_backend.py`. In-scope tests pass cleanly:

```
uv run pytest tests/perception/test_boxer_backend.py tests/test_licenses_md.py tests/perception/test_registry.py -x --timeout=60
# 31 passed, 1 skipped
```

**Required action (future):** Same as Plan 05-05 item — document
`uv sync --extra perception --extra web --extra dev` or reorganize the
`perception` extras into auto-pulled dev deps.

