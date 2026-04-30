---
phase: 05-second-backends-boxer-rtdetr-owlv2
plan: 05
subsystem: perception-infra
tags: [subprocess, zmq, msgpack, threading, registry, boxer, rtdetrv2, crash-fallback, ort]

# Dependency graph
requires:
  - phase: 02-second-detector-modular-refactor
    provides: SubprocessDetectorBridge skeleton (Popen + PAIR socket + msgpack loop)
  - phase: 01-foundation
    provides: _thread_config.py D-04 invariant (_DEFAULT_BUDGET, single thread-budget site)
  - phase: 05-plan-04
    provides: tests/perception/test_crash_fallback.py skip-stubs (bridge_hang_raises, subprocess_died_raises)
provides:
  - BridgeHangError / SubprocessDiedError / BridgeHandshakeError typed exceptions on subprocess_bridge module
  - SubprocessDetectorBridge.wait_for_handshake(timeout_s) — Popen + POLLOUT readiness gate (Open Risk #3)
  - SubprocessDetectorBridge daemon drain thread over merged Popen.stdout/stderr (T-5-05 mitigation)
  - SubprocessDetectorBridge reply-schema docstring extended additively for boxes_3d (D-02)
  - DetectorRegistry.set_available(name, available, reason) — session-scoped override honored by list_backends (D-04)
  - _thread_config.get_default_budget() — public getter over _DEFAULT_BUDGET for ORT backends (D-07)
  - Two activated crash_fallback unit tests (bridge_hang_raises, subprocess_died_raises) — skip-stub → real assertion
affects: [05-06-boxer-backend, 05-07-rtdetrv2-backend, 05-09-pool-crash-handler, 05-11-integration]

# Tech tracking
tech-stack:
  added:
    - pytest-timeout>=2.4.0 (dev dep — required by pytest.ini timeout=30 directive)
  patterns:
    - Typed transport exceptions replace silent None-return failure paths
    - zmq.Poller(POLLOUT) handshake pattern for PAIR-socket worker readiness
    - Daemon drain thread with stderr=STDOUT + bufsize=1 text mode for PIPE-DoS mitigation
    - Session-scoped availability override via per-backend _override_available tuple
    - Public getter over module-private _DEFAULT_BUDGET (no underscore reach-in from backends)

key-files:
  created: []
  modified:
    - src/perception/subprocess_bridge.py
    - src/perception/registry.py
    - src/_thread_config.py
    - tests/perception/test_subprocess_bridge.py
    - tests/perception/test_subprocess_bridge_skeleton.py
    - tests/perception/test_crash_fallback.py
    - tests/perception/test_registry.py
    - tests/perception/test_thread_config.py
    - pyproject.toml
    - uv.lock
    - .planning/phases/05-second-backends-boxer-rtdetr-owlv2/deferred-items.md

key-decisions:
  - "Handshake gate implemented via zmq.Poller(POLLOUT) + Popen.poll loop in 100ms slices — no PING/PONG wire-protocol invention (SLAM bridge lacks such handshake; PAIR POLLOUT flips only when peer connects)"
  - "BridgeHandshakeError reserved class added proactively for future strict-protocol handshakes — current handshake only needs BridgeHangError (timeout) + SubprocessDiedError (early exit)"
  - "Popen stdout/stderr merged via stderr=STDOUT so a single drain thread covers both — avoids two threads racing two pipes"
  - "set_available's override dict is stored inside _backends[name]['_override_available'] so _clear() wipes it automatically without extra state-clearing code"
  - "list_backends still surfaces 'Cannot load ...' BEFORE evaluating the override — a missing class path cannot be overridden into availability"

patterns-established:
  - "Pattern: transport failure paths raise typed exceptions (not return None) so pool crash handler can catch the exact failure mode"
  - "Pattern: POLLOUT-readiness handshake for PAIR sockets (future subprocess backends in v2+ SLAM or detectors can copy this)"
  - "Pattern: daemon drain thread over merged Popen pipe — reusable in any subprocess-worker bridge"
  - "Pattern: session-scoped availability override via registry — future phases may generalize to SLAM backend registry if a crash handler is added there"

requirements-completed: [DET-MODELS-03, DET-MODELS-06]

# Metrics
duration: ~35min
completed: 2026-04-15
---

# Phase 5 Plan 05: Bridge Typed Exceptions, Handshake, Drain Thread + Registry Override Summary

**SubprocessDetectorBridge hardened with typed BridgeHangError/SubprocessDiedError, POLLOUT handshake, and daemon stdout-drain thread; DetectorRegistry gains set_available for D-04 post-crash lockout; _thread_config exposes get_default_budget for ORT consumers.**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-04-15T03:32:00Z (approx)
- **Completed:** 2026-04-15T04:07:39Z
- **Tasks:** 2 (each TDD: RED → GREEN)
- **Files modified:** 11 (3 source + 5 test + 3 config/deferred)

## Accomplishments

- Bridge `send_frame`'s four failure paths (not-alive / Popen-died / zmq.Again / zmq.ZMQError+generic) now raise typed exceptions. The pool crash handler in Plan 05-09 can catch the exact failure mode instead of branching on a silent None sentinel.
- `wait_for_handshake(timeout_s)` mitigates Open Risk #3 — BoxeR's 5–15 s weight load no longer races the first `send_frame`. The gate polls both Popen liveness and `zmq.Poller(POLLOUT)` so it fails fast on early worker exit.
- Daemon drain thread over merged `Popen.stdout` (stderr=STDOUT) mitigates T-5-05 — a chatty worker whose stdout would fill the 64 KB pipe buffer is drained into `logger.info` with the worker PID prefix. Verified via a synthesized 128-lines-per-frame "chatty worker" fixture running 10 frames without hang.
- `DetectorRegistry.set_available(name, available, reason)` overrides probe result inside `list_backends`. Unknown backends raise `ValueError`; `True + None` restores probe, `False + reason` or `False + None` (default message fallback) locks out.
- `_thread_config.get_default_budget()` exposes `_DEFAULT_BUDGET` as a public function — Plan 05-07's RT-DETRv2 backend will set `sess_options.intra_op_num_threads = get_default_budget()` without violating the Phase 1 D-04 "no thread budget outside _thread_config" invariant.
- Two crash_fallback skip-stubs (bridge_hang_raises, subprocess_died_raises) activated with real assertions running against the echo worker (-- sleep-ms 2000 for hang, Popen.kill for death).

## Task Commits

Each task was TDD'd (RED → GREEN) and committed atomically:

1. **Task 1 RED: bridge typed exceptions + handshake + drain-thread tests** — `6476312` (test)
2. **Task 1 GREEN: bridge typed exceptions, handshake, stdout drain thread** — `a4cee04` (feat)
3. **Plan-level chore: pytest-timeout dev dep + deferred-items log** — `75fe3ab` (chore)
4. **Task 2 RED: DetectorRegistry.set_available + get_default_budget tests** — `4ba0c88` (test)
5. **Task 2 GREEN: DetectorRegistry.set_available + get_default_budget getter** — `c83d481` (feat)

_Note: RED commits intentionally leave tests failing (import errors) so the subsequent GREEN commit can be verified in isolation._

## Files Created/Modified

- `src/perception/subprocess_bridge.py` — added 3 exception classes, `wait_for_handshake`, `_drain_worker_output`, Popen config flip (stderr=STDOUT + bufsize=1 + text), drain thread lifecycle in start/_kill_process, typed raises in `send_frame`, `boxes_3d` additive docstring (D-02), `_now` clock seam
- `src/perception/registry.py` — added `DetectorRegistry.set_available`, override branch in `list_backends`, docstring update for `_clear`
- `src/_thread_config.py` — added `get_default_budget()` public getter
- `tests/perception/test_subprocess_bridge.py` — flipped kill-test to `pytest.raises`, added 4 new tests (pre-start raises, handshake success, handshake dead-worker, chatty-worker drain)
- `tests/perception/test_subprocess_bridge_skeleton.py` — flipped pre-start assertion to `pytest.raises(SubprocessDiedError)`
- `tests/perception/test_crash_fallback.py` — activated 2 skip-stubs with real assertions
- `tests/perception/test_registry.py` — added 4 tests for `set_available` behaviors
- `tests/perception/test_thread_config.py` — added 1 test for `get_default_budget`
- `pyproject.toml` + `uv.lock` — added `pytest-timeout>=2.4.0` to `[dependency-groups].dev`
- `.planning/phases/05-second-backends-boxer-rtdetr-owlv2/deferred-items.md` — logged pre-existing fastapi/torch/open3d install-profile test failures as out-of-scope

## Decisions Made

- **POLLOUT-based handshake, not PING/PONG wire protocol.** The plan suggested mirroring a SLAM bridge handshake if present, but the SLAM bridge has no handshake (grep confirmed). Inventing a PING/PONG would fork the msgpack schema and require the echo worker + future BoxeR worker to implement it. `zmq.Poller(POLLOUT)` on a PAIR socket flips writable only after the peer calls `connect()` — this is a reliable existence signal without any protocol change. The loop polls in 100 ms slices so Popen death is observed promptly.
- **`BridgeHandshakeError` class added even though no caller raises it.** The plan's `must_haves/truths` only requires BridgeHangError + SubprocessDiedError, but the task description mentions a handshake-error class conceptually. Adding it reserves the name + type for future strict-protocol handshakes (e.g. schema negotiation). Zero cost today; non-breaking addition. Documented in the docstring.
- **stderr merged into stdout via `stderr=STDOUT`** — single daemon drain thread covers both streams, avoiding a two-thread dance over two pipes. Worker PID is prefixed into every log line (`[worker 1234] ...`).
- **Override stored inside per-backend `_backends[name]` dict, not a parallel `_override_available` dict on the registry class.** Simpler lifecycle: `_clear()` drops it automatically without new state-clearing code; `list_backends` reads with `.get("_override_available")` and branches cleanly.
- **`list_backends` applies the klass-load check BEFORE evaluating the override.** A `set_available(True, None)` call on a backend whose class cannot import would otherwise falsely surface it as available. The klass-load path still wins because the override is only meaningful when the class is loadable.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Missing `pytest-timeout` dev dependency**
- **Found during:** Task 1 RED baseline run
- **Issue:** `pytest.ini` declares `timeout = 30` which requires the `pytest-timeout` plugin. Without it, pytest errors out at startup with `unrecognized arguments: --timeout=30` — the plan's verification commands (all use `--timeout=30` or `--timeout=60`) would be un-runnable. Plan 05-01 added `[slow_boxer, network]` markers but missed this plugin.
- **Fix:** `uv add --dev pytest-timeout>=2.4.0`
- **Files modified:** `pyproject.toml`, `uv.lock`
- **Verification:** All 05-05 verification commands now run (`pytest ... --timeout=30` exits clean)
- **Committed in:** `75fe3ab`

**2. [Out-of-scope discoveries — NOT auto-fixed; logged to deferred-items.md]**
- **Found during:** Phase-level regression command `uv run pytest tests/ -m "not slow_boxer and not network"`
- **Issue:** Eight collection errors (fastapi missing) and three runtime failures (torch, open3d missing) across `tests/mcp`, `tests/web`, `tests/perception/test_protocol_contracts.py`, `tests/perception/test_point_cluster_lifter.py`, `tests/slam/test_openvins_backend.py`, `tests/integration/test_multi_*`. All caused by missing optional extras in the base `uv sync` profile (no `[perception]`, `[web]` extras auto-installed).
- **Why not fixed:** SCOPE BOUNDARY rule — these failures exist on the pre-05-05 base (commit 10202b7) and are caused by dev-install profile mismatches, not the bridge changes in 05-05. The narrow plan-scope verification (`tests/perception/test_subprocess_bridge*.py test_crash_fallback.py test_registry.py test_thread_config.py --timeout=30`) passes 130/130 cleanly. Phase-level CI hygiene is Phase 6+ concern.
- **Logged:** `.planning/phases/05-second-backends-boxer-rtdetr-owlv2/deferred-items.md`
- **Committed in:** `75fe3ab`

---

**Total deviations:** 1 auto-fixed (Rule 3 - blocking infra) + 1 logged-to-deferred (scope boundary)
**Impact on plan:** No scope creep. The `pytest-timeout` add is a one-line dev-dep that Plan 05-01 should have caught; everything else is pre-existing test-infra debt on a minimal venv profile.

## Issues Encountered

- **Worktree started ahead of expected base.** Initial `HEAD` was `7fc7f32` (end of Plan 05-03) but the prompt specified `EXPECTED_BASE=10202b7` (end of Plan 05-04 merge). `git reset --hard 10202b7` applied per the worktree_branch_check directive — Plan 04's skip-stub test file is required context for this plan's "activate two tests" task.
- **`sys.modules` pollution concern around `_clean_registries` autouse fixture.** The new `set_available` tests all use registered backends via the test-local `Probed_*` classes and the autouse fixture clears after each — no issue. The fixture pops `src.perception.backends` but NOT `src.perception.registry`, so the DetectorRegistry class identity stays stable across tests. Verified with `pytest -v` — no cross-test contamination.

## Known Stubs

None introduced. The three remaining `pytest.skip` stubs in `tests/perception/test_crash_fallback.py` (`test_pool_on_backend_crash_emits_ws_message`, `test_pool_swaps_to_yolo`, `test_pool_marks_crashed_backend_unavailable`) are **Plan 05-09's** territory, not 05-05's. Plan 05-05's scope explicitly covers only the bridge-level two (`test_bridge_hang_raises`, `test_subprocess_died_raises`) — both activated.

## User Setup Required

None — this plan ships pure infrastructure under `src/perception/` + `src/_thread_config.py`. No new env vars, no new services, no checkpoint fetches.

## Next Phase Readiness

**Ready for Wave 2 (05-06 BoxeR backend, 05-07 RT-DETRv2 backend, 05-09 pool crash handler):**

- `BoxerBackend.warmup()` (Plan 05-06) can compose `SubprocessDetectorBridge`, call `bridge.start()` then `bridge.wait_for_handshake(timeout_s=60.0)` before returning — the warmup overlay gate (Phase 3 D-15) stays tight.
- `RTDETRv2Backend.__init__` (Plan 05-07) can set `sess_options.intra_op_num_threads = get_default_budget()` without triggering the `test_no_module_scope_set_num_threads` grep invariant.
- `DetectorWorkerPool.on_backend_crash` (Plan 05-09) can `except (BridgeHangError, SubprocessDiedError)` at the worker's `bridge.send_frame` call site, emit `crash_fallback` WS, `DetectorRegistry.set_available("boxer", False, reason="Crashed this session — restart the coordinator to retry.")`, and atomically swap to YOLOv11 under `_swap_lock`.

**No blockers** for downstream plans. The `BridgeHandshakeError` reserved class is not consumed anywhere yet — downstream plans can adopt it if a schema-negotiation handshake is added later.

## Self-Check: PASSED

**Files verified (all FOUND):**
- `src/perception/subprocess_bridge.py` — modified (contains `class BridgeHangError`, `class SubprocessDiedError`, `class BridgeHandshakeError`, `def wait_for_handshake`, `def _drain_worker_output`, `boxes_3d` in docstring, `stderr=subprocess.STDOUT`)
- `src/perception/registry.py` — modified (contains `def set_available`, `_override_available`)
- `src/_thread_config.py` — modified (contains `def get_default_budget`)
- `tests/perception/test_subprocess_bridge.py` — modified (flipped to pytest.raises + 4 new tests)
- `tests/perception/test_subprocess_bridge_skeleton.py` — modified (pre-start raises SubprocessDiedError)
- `tests/perception/test_crash_fallback.py` — modified (2 skip-stubs activated)
- `tests/perception/test_registry.py` — modified (4 set_available tests)
- `tests/perception/test_thread_config.py` — modified (1 get_default_budget test)
- `pyproject.toml` + `uv.lock` — modified (pytest-timeout added)
- `.planning/phases/05-second-backends-boxer-rtdetr-owlv2/deferred-items.md` — modified (scope boundary log)

**Commits verified (all FOUND via `git log --oneline 10202b7..HEAD`):**
- `6476312` test(05-05): RED — bridge typed exceptions, handshake, drain-thread tests
- `a4cee04` feat(05-05): bridge typed exceptions, handshake, stdout drain thread
- `75fe3ab` chore(05-05): add pytest-timeout dev dep + log deferred scope items
- `4ba0c88` test(05-05): RED — DetectorRegistry.set_available + get_default_budget
- `c83d481` feat(05-05): DetectorRegistry.set_available + get_default_budget getter

**Acceptance criteria — all 10 verified:**
- `grep -c "^class BridgeHangError(RuntimeError):" src/perception/subprocess_bridge.py` → 1 ✓
- `grep -c "^class SubprocessDiedError(RuntimeError):" src/perception/subprocess_bridge.py` → 1 ✓
- `grep -c "def wait_for_handshake" src/perception/subprocess_bridge.py` → 1 ✓
- `grep -c "def _drain_worker_output" src/perception/subprocess_bridge.py` → 1 ✓
- `grep -c "boxes_3d" src/perception/subprocess_bridge.py` → 3 ✓ (≥ 1)
- `grep -c "return None" src/perception/subprocess_bridge.py` → 1 ✓ (≤ 2 — only drain-thread guard)
- `grep -c "raise BridgeHangError" src/perception/subprocess_bridge.py` → 2 ✓ (≥ 2: send_frame + wait_for_handshake)
- `grep -c "raise SubprocessDiedError" src/perception/subprocess_bridge.py` → 6 ✓ (≥ 3: not-alive + popen-died + zmq-error + generic-exc + 2 handshake paths)
- `grep -c "def set_available" src/perception/registry.py` → 1 ✓
- `grep -c "_override_available" src/perception/registry.py` → 2 ✓ (≥ 2)
- `grep -c "def get_default_budget" src/_thread_config.py` → 1 ✓
- `grep -c "pytest.skip" tests/perception/test_crash_fallback.py` → 3 ✓ (≤ 3 — two activated, three pending Plan 09)

**Plan-scope pytest run:** `130 passed, 4 skipped, 2 warnings in 6.97s` — all 5 plan-scope test files green.

---
*Phase: 05-second-backends-boxer-rtdetr-owlv2*
*Completed: 2026-04-15*
