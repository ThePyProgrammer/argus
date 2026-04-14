---
phase: 02-per-robot-worker-and-wire-plumbing
plan: 07
subsystem: perception
tags: [perception, subprocess, zmq, msgpack, handshake, test-harness, ipc]

requires:
  - phase: 02-per-robot-worker-and-wire-plumbing
    provides: "SubprocessDetectorBridge skeleton (Plan 02-06) — PAIR bind, msgpack ingress, HANG_TIMEOUT_MS=5000, _kill_process cleanup"
provides:
  - "Permanent repo helper scripts/echo_detector_worker.py (D-15) — standalone ZMQ PAIR echo worker with fixed 0-detection reply"
  - "Full D-17 handshake coverage for SubprocessDetectorBridge: spawn, multipart send, msgpack round-trip, slow-backend path, external kill timeout, /tmp IPC cleanup"
  - "Phase 5 BoxeR dev harness: run echo worker in one terminal, drive it from Python REPL in another"
affects:
  - "Phase 5 DET-MODELS-03 (BoxeR backend composes SubprocessDetectorBridge and reuses this reply schema)"
  - "Any future out-of-process detector/tracker that needs a ZMQ PAIR + msgpack transport"

tech-stack:
  added: []
  patterns:
    - "Shebang-based Popen invocation of Python helper scripts (chmod +x + #!/usr/bin/env python3)"
    - "Test-infra PATH prepend of .venv/bin so env-based shebangs resolve to the interpreter with test deps"
    - "PAIR client (worker) ↔ PAIR server (bridge) with msgpack multipart frames — fixed reply schema at Phase 2 boundary"

key-files:
  created:
    - "scripts/echo_detector_worker.py"
    - "tests/perception/test_subprocess_bridge.py"
  modified: []

key-decisions:
  - "Use shebang + chmod +x on echo worker so SubprocessDetectorBridge.start() can Popen it directly via binary_path=ECHO_SCRIPT (sidesteps the [python, --zmq, endpoint, script] argv-order problem the plan flagged)"
  - "Prepend .venv/bin to PATH in the test module (not in the worker script) — production deployments already have msgpack+zmq on the first python3 in PATH; the workaround stays scoped to test infra"
  - "Echo worker reply schema is locked at {ts, inference_ms, n_det, classes, scores, bboxes} — Phase 5 BoxeR backend must produce the same keys (bridge's strict_map_key=True will reject drift)"

patterns-established:
  - "Out-of-process detector workers connect PAIR-client to the bridge-bound endpoint (bridge always binds, worker always connects)"
  - "Worker replies are single-part msgpack (header IS the whole reply); incoming frames are multipart ([header, rgb, depth?])"
  - "IPC socket file at /tmp/detector_bridge_<pid>_<id(self)> is unlinked by _cleanup() — tests assert the file is gone after shutdown()"

requirements-completed: [DET-MODELS-05]

duration: ~10 min
completed: 2026-04-14
---

# Phase 2 Plan 07: SubprocessDetectorBridge Handshake Test + Echo Worker Summary

**Permanent ZMQ PAIR echo worker + 7-test handshake suite locking the D-17 detector-worker transport protocol (spawn, multipart send, msgpack round-trip, slow backend, external kill, /tmp cleanup) before Phase 5 BoxeR builds on it.**

## Performance

- **Duration:** ~10 min
- **Completed:** 2026-04-14T02:36:55Z
- **Tasks:** 2
- **Files created:** 2 (96 + 256 lines)

## Accomplishments

- **D-15 permanent helper shipped:** `scripts/echo_detector_worker.py` is checked into the repo (not tests/fixtures/), executable via shebang, and reusable as a Phase 5 BoxeR dev harness.
- **D-17 handshake surface fully proven:** 7 tests cover the complete transport — spawn, multipart send, msgpack header fidelity, slow-backend simulation (`--sleep-ms`), external SIGKILL → watchdog, IPC socket file cleanup, zmq context/socket reference nulling.
- **No /tmp leaks:** `test_shutdown_cleans_up_ipc_socket_file` asserts `os.path.exists(sock_path) is False` after `bridge.shutdown()`.
- **Full run time 2.47 s** — well under the 15 s plan budget.

## Task Commits

1. **Task 1: echo worker script** — `47bf293` (feat)
2. **Task 2: D-17 handshake test suite** — `b53b4a2` (test)

_Plan metadata commit follows via the parallel-mode merge-back; this SUMMARY is the final per-plan artifact._

## Files Created

- **`scripts/echo_detector_worker.py`** (96 lines, chmod +x)
  - CLI: `--zmq <endpoint>` (required), `--sleep-ms N` (optional, default 0)
  - Connects `zmq.PAIR` client socket to the bridge-bound endpoint
  - Loop: `recv_multipart` → unpack header (`raw=False`) → optional `time.sleep(sleep_ms/1000)` → reply `msgpack.packb({ts, inference_ms, n_det:0, classes:[], scores:[], bboxes:[]})`
  - Clean exit on `KeyboardInterrupt` / `zmq.ContextTerminated` with `sock.close(linger=0)` + `ctx.term()`

- **`tests/perception/test_subprocess_bridge.py`** (256 lines, 7 tests)

  | Test | D-17 Coverage |
  |------|---------------|
  | `test_endpoint_prefix_distinct_from_slam` | D-16 namespace isolation (no `slam_bridge_` collision) |
  | `test_spawn_send_recv_round_trip` | Popen worker → multipart send → msgpack dict reply with all 6 required keys |
  | `test_msgpack_header_fidelity` | Worker echoes `header['ts']=7.5` back with `abs(reply['ts']-7.5)<1e-9` |
  | `test_slow_backend_still_returns_before_timeout` | `--sleep-ms 200` → reply in <1 s (200 ms ≪ 5 s `HANG_TIMEOUT_MS`) |
  | `test_kill_triggers_none_reply_within_timeout` | `os.kill(worker_pid, SIGKILL)` → next `send_frame` returns `None` within 5 s; `bridge.alive` flips `False` |
  | `test_shutdown_cleans_up_ipc_socket_file` | `os.path.exists(sock_path) is False` after `shutdown()` (Pitfall 3) |
  | `test_shutdown_closes_context_and_socket_handles` | `_cleanup()` nulls `_socket`, `_ctx`, `_process` references |

## Echo Worker CLI Reference

```
$ scripts/echo_detector_worker.py --help
usage: echo_detector_worker.py [-h] --zmq ZMQ_ENDPOINT [--sleep-ms SLEEP_MS]

ZMQ PAIR echo worker for SubprocessDetectorBridge (D-15, D-17).

options:
  --zmq ZMQ_ENDPOINT   ZMQ endpoint to connect to (e.g.,
                       ipc:///tmp/detector_bridge_<pid>_<id>).
  --sleep-ms SLEEP_MS  Simulate slow backend: sleep this many ms per frame
                       before replying.
```

**Manual dev-harness usage (Phase 5 BoxeR bring-up):**

```python
# Terminal 1: start a bridge that binds and spawns the echo worker.
from src.perception.subprocess_bridge import SubprocessDetectorBridge
bridge = SubprocessDetectorBridge(
    binary_path="scripts/echo_detector_worker.py",
    args=["--sleep-ms", "50"],
)
bridge.start()

# Drive synthetic frames through and inspect replies.
import numpy as np
rgb = np.zeros((480, 640, 3), np.uint8)
depth = np.full((480, 640), 2.0, np.float32)
reply = bridge.send_frame(rgb, depth, timestamp=0.0)
# reply == {"ts": 0.0, "inference_ms": 50.0, "n_det": 0, "classes": [], "scores": [], "bboxes": []}

bridge.shutdown()  # unlinks /tmp/detector_bridge_<pid>_<id>
```

## Decisions Made

**1. Shebang-based Popen invocation (not `sys.executable` + script argv).**
The bridge constructs `cmd = [binary_path, "--zmq", endpoint, *args]`. Using `binary_path=sys.executable` with `args=[ECHO_SCRIPT]` would produce `[python, "--zmq", endpoint, ECHO_SCRIPT]` — python rejects `--zmq` before the script name. The plan called this out and selected `os.chmod(ECHO_SCRIPT, 0o755)` + `binary_path=ECHO_SCRIPT`, leaning on `#!/usr/bin/env python3`. Implemented that exactly, with `chmod +x` both at file-creation time (Task 1) and at test-module import time (belt-and-suspenders).

**2. PATH prepend in test, not worker.**
In a uv-managed checkout, the test runs under `.venv/bin/python3.12` but Popen's shebang resolution uses the first `python3` on `PATH`, which is the system 3.14 interpreter — no `msgpack`/`zmq` installed. Fixed at test-infra level: `os.environ["PATH"] = f"{.venv/bin}:{PATH}"` at module import. Kept out of the worker script itself so production deployments (where `msgpack`/`zmq` are on the first `python3`) don't carry test-only plumbing.

**3. Strict reply-schema contract for Phase 5.**
Bridge decodes replies with `raw=False, strict_map_key=True` (Plan 02-06). Any Phase 5 BoxeR worker that drifts from `{ts, inference_ms, n_det, classes, scores, bboxes}` or uses non-string keys will fail fast at the `msgpack.unpackb` call, not silently downstream. Documented in the summary for the next phase.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Test-time PATH resolution for the echo worker's Python shebang**
- **Found during:** Task 2 (first full test run)
- **Issue:** The bridge's `Popen([ECHO_SCRIPT, "--zmq", ...])` invokes the worker via `#!/usr/bin/env python3`. In this uv-managed checkout the first `python3` on `PATH` resolves to system Python 3.14, which has no `msgpack`/`zmq` — worker exited with code 1, bridge saw crash via `Popen.poll()` and returned `None`.
- **Fix:** Added a test-module-level `os.environ["PATH"] = f"{sys.executable.parent}:{PATH}"` so subprocess children inherit a PATH that finds the venv's `python3` (3.12, with msgpack+zmq) first.
- **Files modified:** `tests/perception/test_subprocess_bridge.py` (PATH-prepend block near the top, fully commented).
- **Verification:** All 7 tests pass; `ls /tmp/detector_bridge_*` empty after the run.
- **Committed in:** `b53b4a2` (Task 2 commit)

**2. [Rule 2 - Missing Critical] Added `test_shutdown_closes_context_and_socket_handles`**
- **Found during:** Task 2 authoring
- **Issue:** Plan's must_haves/truths names "closes zmq context (no leaked fds)" as part of the _kill_process cleanup surface, and Pitfall 3 is about IPC file leaks. The plan's 6 listed tests cover the /tmp file but don't explicitly assert the `_socket`/`_ctx`/`_process` references are nulled after `shutdown()`.
- **Fix:** Added a 7th test asserting `b._socket is None`, `b._ctx is None`, `b._process is None` after `shutdown()`. This is the closest-to-fd-leak check we can do without parsing `/proc/<pid>/fd/` — covers the reference-nulling contract in `_cleanup()`.
- **Files modified:** `tests/perception/test_subprocess_bridge.py` (extra test at end).
- **Verification:** Test green; bridge correctly nulls all three handles in `_cleanup()` / `_kill_process()`.
- **Committed in:** `b53b4a2` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 missing critical)
**Impact on plan:** Both fixes stay inside the handshake surface the plan targets. Test count went from 6 → 7 — still under the 15 s runtime budget (actual: 2.47 s). No scope creep.

## Issues Encountered

- `uv run pytest` falls through to the user's `~/.local/bin/pytest` on system Python 3.14 instead of the venv's interpreter. Resolved by installing pytest into the venv (`uv sync --extra dev`) and invoking `.venv/bin/pytest` directly. Noted here for any follow-on agent running tests in this worktree.

## Threat Flags

None — this plan only adds a permanent helper script and a test file. No new trust boundaries, endpoints, or schema extensions beyond what D-17 already locked in Plan 02-06. The new threats (T-02-16 through T-02-18) registered in the PLAN are all dispositioned `accept` / `mitigate` via the pytest fixture `try/finally`, which is implemented.

## Next Phase Readiness

- **Phase 5 (DET-MODELS-03) can start BoxeR backend work.** `SubprocessDetectorBridge` is proven on the transport layer; BoxeR composes the bridge and replaces the echo worker with real inference. Reply schema is locked — any deviation will trigger the bridge's `strict_map_key=True` ingress defence.
- **Echo worker doubles as Phase 5 smoke harness:** run `scripts/echo_detector_worker.py` standalone to sanity-check ZMQ plumbing on a new dev box before wiring up CUDA/BoxeR.

---

## Self-Check: PASSED

**Created files verified on disk:**
- `scripts/echo_detector_worker.py` — FOUND (96 lines, mode 755)
- `tests/perception/test_subprocess_bridge.py` — FOUND (256 lines)

**Commits verified in git log:**
- `47bf293` (Task 1: feat echo worker) — FOUND
- `b53b4a2` (Task 2: test D-17 handshake) — FOUND

**Verification commands rerun:**
- `python scripts/echo_detector_worker.py --help` → exits 0, prints usage
- `.venv/bin/pytest tests/perception/test_subprocess_bridge.py -v` → 7/7 passed in 2.47 s
- `ls /tmp/detector_bridge_*` → no matches (no leaked socket files)

---
*Phase: 02-per-robot-worker-and-wire-plumbing*
*Completed: 2026-04-14*
