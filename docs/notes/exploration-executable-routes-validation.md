# Executable route selection — Issue #8

## Development contract, frozen before new live outcomes

The planner will compare forward and backward waypoint following using a
bounded nominal forecast on the observed map. Each forecast command uses the
existing clearance guard, including command response, unknown center cells,
and stopping tails. Prediction must not mutate live guard or runner history.
Every real command is checked again. Geometry, map observations, clearance
allowances, retry counts, and blockage deadlines remain unchanged.

Route acceptance requires 0.15 m of predicted translation within four seconds;
turning or standing drift cannot meet that threshold. This is a local ranking
heuristic, not a whole-route or physical dynamics guarantee. The nominal
forecast uses the shared gait yaw/restart filter and the guard's acceleration
parameter. Its hypothetical observation times assume the frozen map remains
available; the first check enforces actual observation freshness. Real commands
always use actual sensor times.

Search remains capped at 32 goals and two travel directions per goal. Recovery
compares at most four existing primitives, their predicted directed-progress
endpoints and standing intervals, and four goals per endpoint. It prefers a
predicted navigable endpoint. If none is found, a bounded admitted sensing
motion may still reveal free space; that is explicitly not a successful escape.
Only observed translation on an installed route resets the blockage budget.

The frozen clutter-101 terminal fixture preserves the observed map, estimated
body pose, radius, configuration, and source hash. Its stationary settled
history is hypothetical; it does not reconstruct the recorded gait history.
It must reject the original turning proposals and select a later executable
backward route. Analytical fixtures cover stale inputs, unknown space, preview
isolation and recovery followed by navigation; physical fixtures cover actual
commanded progress and stopped traps.

Fresh paired development attempts will use clutter seeds 101/102 with requested
16-second horizons and connected rooms seed 101 for a five-second regression.
Compare with the preserved pose/map matrix and bounded-recovery runs. An
improved recoverable case must have accepted navigation translation spanning
at least two seconds and at least 0.30 m of net route displacement after the
old policy's first blockage, positive coverage gain, zero non-foot contacts,
and zero falls. Report every early failure and remaining trap. These are
development criteria; broader long-horizon acceptance remains Issue #11.

Use `scripts/validate_exploration.py` with new directories, hold runtime sources
unchanged through video export, and link every attempt's verified video. Report
actual/requested duration, initial/final coverage, movement, recovery, contact
severity, pose/floor diagnostics, and unresolved clearance rejections.

## Implementation and regression evidence

Runtime `15bc2a9` implements the preview and endpoint ranking. A rejected
geometric route now produces `no_executable_route` with per-candidate reasons,
instead of being installed and immediately rejected during execution. Backward
following aligns the rear toward the same geometric path and caps its speed at
the existing 0.60 m/s recovery proposal. Forward behavior remains available;
the admitted mode requiring fewer forecast steps is preferred, with forward
as the deterministic tie-breaker.

The terminal fixture rejects the first geometrically valid turning route and
admits a later backward route without changing any observed cells. The real
physics fixtures demonstrate retreat followed by accepted navigation in both
lateral and backward escape cases, a stopped trap, and expiration of a forced
forward-only long turn. All four have zero non-foot contacts. The long-turn
fixture deliberately retains the old follower to keep testing turning drift;
normal selection now escapes that fixture backward.

On November 21, 2026, the affected suite passes **1,109 tests with nine skips**
in **291.74 seconds**, including the SLAM suite. Command:

```powershell
$env:OMP_NUM_THREADS = '1'
.venv/Scripts/python.exe -m pytest tests/exploration tests/control tests/coordination tests/bridge tests/metrics/test_exploration_coverage.py tests/locomotion/test_gait_controller.py tests/locomotion/test_gait_clearance.py tests/locomotion/test_gait_transitions.py tests/locomotion/test_locomotion.py tests/slam -q -p no:cacheprovider --basetemp=outputs/exploration-planning/executable-routes/test-regression-02
```

The first broad run hit Windows sandbox temporary-directory access errors and
could not finish pytest cleanup. A separate run exposed an outdated assertion
that every geometric route must receive a goal assignment. The updated fixture
requires either an admitted preview and assignment or explicit rejection of
every preview with `no_executable_route`. Exact collector-on/off command and
body-state equality remains required and passes. The final suite ran outside
the sandbox with a fresh temporary directory. Logs remain in
`outputs/exploration-planning/executable-routes/`; the unsupported IPC transport
tests remain skipped, not presented as native IPC validation.

## Initial live failures and corrections

The initial runtime (`15bc2a9`, launched at documentation revision `1d13ef7`)
regressed against the preserved baselines. All three attempts completed their
artifact workflow, retained unchanged runtime sources through export, and have
zero non-foot contacts, non-foot force/impulse, falls, missed diagnostic floor
samples, and removed samples above 4 cm. Those clean measurements do not make
the navigation outcomes successful.

| Attempt | Actual/requested time | Initial/final coverage | Outcome | Verified body states |
| --- | --- | --- | --- | --- |
| [Clutter 101, initial](../../outputs/exploration-planning/executable-routes/clutter-s101-live-01/top-view.mp4) | 11.22/16 s | 14.6569/23.9706% | `navigation_failed` | 1,123, zero replay error |
| [Clutter 102, initial](../../outputs/exploration-planning/executable-routes/clutter-s102-live-01/top-view.mp4) | 12.29/16 s | 37.7288/62.4673% | `navigation_failed` | 1,230, zero replay error |
| [Connected rooms 101, initial](../../outputs/exploration-planning/executable-routes/connected-s101-live-01/top-view.mp4) | 5.00/5 s | 58.2179/60.4154% | Horizon, no accepted navigation translation | 501, zero replay error |

The preserved baselines finish at 31.4379%, 72.5654%, and 77.1523% respectively.
The new preview frequently reports `route_complete` without 15 cm of predicted
travel: the follower's 30 cm arrival ball finishes goals only just outside the
30 cm candidate-exclusion distance. Runtime `e0636d5` approaches selected
frontier members to within one map cell (capped by the configured arrival
threshold). This changes goal completion, not obstacle inflation, body geometry,
the execution guard, or the frozen 15 cm progress requirement.

Clutter-102 B additionally walks backward on navigation commands from 9.66 to
12.29 s: 0.18390 m net true displacement and 0.18465 m estimated. Replacing
its route at 11.07 s resets the navigation anchor, so it still expires with
`blocked_timeout`. The correction preserves an existing walking anchor across
route replacement. Every turning/idle observation still resets it, and
blocked/recovery transitions still start a new interval. Merely installing
another route cannot reset retries or the deadline.

The correction was developed in an isolated checkout while the initial attempts
kept their original runtime. The checkout's missing unrelated Git LFS office
assets were excluded; the Go2 assets and frozen terminal fixture were copied
from the main checkout. One first test invocation encountered an unmaterialized
LFS pointer; after restoring the fixture, the corrected focused suite passes
**32 tests in 73.71 seconds**. The added physical nearby-frontier case proves
actual retreat followed by accepted navigation translation with zero non-foot
contacts. The corrected implementation was merged only after all initial video
exports completed.
