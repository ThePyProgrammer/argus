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

The complete affected suite at `e0636d5` passes **1,112 tests with nine skips**
in **585.55 seconds** (`regression-03.log`). It uses the same command and suite
selection above with fresh temporary directory `test-regression-03`, outside
the Windows sandbox. The additional nearby-goal, physical nearby-frontier,
and continuous-walking-anchor regressions are included. Runtime files remain
unchanged during the corrected live comparisons.

## Corrected live evidence at `e0636d5`

The [corrected connected-room video](../../outputs/exploration-planning/executable-routes/connected-s101-live-02/top-view.mp4)
reaches **5.00/5.00 s**, with **58.2179% initial coverage, 71.5081% final
coverage**, normalized coverage AUC **0.687823**, and **1.01224 m** team travel.
There are zero non-foot contacts, non-foot force/impulse, falls, recoveries,
execution rejections, missed diagnostic floor samples, or removals above 4 cm.
Both robots finish navigating. All **501 body states** verify with zero replay
error, and runtime source hashes match both before and after video export.

Coverage remains below the original baseline's **77.1523%**. A receives 2.91 s
of accepted backward navigation and moves 0.07864 m net during that interval;
B receives 1.43 s across two intervals. Summed movement projected along the
commanded direction is only **+0.04927 m for A and -0.02988 m for B**. These
diagnostic projections exclude turning, standing, bootstrap, and recovery.
They show that nominally admitted commands need not produce the predicted
body motion. This run improves the first implementation's 60.4154% coverage
and eliminates its route-completion rejection, but is not evidence of the
frozen sustained-progress criterion or improved coverage over the old policy.

Both corrected clutter attempts also reach the full requested horizon. Their
source hashes remain unchanged through export, and each video verifies all
**1,601 body states with zero replay error**. Both have zero non-foot contacts,
non-foot force/impulse, falls, missed diagnostic floor samples, and removed
samples above 4 cm.

| Attempt | Actual/requested time | Initial/final coverage | Normalized coverage AUC | Team travel |
| --- | --- | --- | --- | --- |
| [Clutter 101, corrected](../../outputs/exploration-planning/executable-routes/clutter-s101-live-02/top-view.mp4) | 16.00/16 s | 14.6569/23.6438% | 0.228289 | 1.63786 m |
| [Clutter 102, corrected](../../outputs/exploration-planning/executable-routes/clutter-s102-live-02/top-view.mp4) | 16.00/16 s | 37.7288/78.7418% | 0.701475 | 3.16366 m |

Clutter-101 A receives **9.20 s of accepted navigation translation**, including
an uninterrupted **5.87 s interval from 4.20 to 10.07 s** with **0.32962 m net
true displacement** (0.32992 m estimated). This interval follows the old
policy's first blockage at 3.23 s. Coverage grows from **23.1863% at 3.23 s to
23.6438%**. The frozen two-second/0.30 m progress criterion, positive coverage
gain, and clean measured contact/fall requirements are therefore met. Summed
displacement along accepted navigation command directions is **0.70291 m**;
turning, standing, bootstrap, and recovery are excluded.

A ends with `navigation_progress`, no active blockage deadline, and no recovery
attempts. It still has two execution rejections and a later no-progress stop,
handled within the existing retry limits. B remains stopped, reporting
`no_safe_recovery` at **3.03 s**, after two replans and one recovery selection:
all four primitives fail clearance. B's failure does not terminate productive
A. Its initial 100 stopping-envelope rejections remain explicit. Exhausting
these candidates is not proof that every possible physical escape is impossible.

Clutter-102 A and B receive **8.34 s and 7.82 s** of accepted navigation
translation, with summed directed displacement of **0.45342 m and 0.25280 m**.
Neither robot attempts a recovery primitive. A clears its blockage budget and
ends with `navigation_progress`. B finishes navigating after a later blockage
at 12.86 s and one replan; that newest blockage budget has not yet reset.
There are two execution rejections for A and none for B; A also records eight
stopping-envelope rejections. Reaching the horizon does not erase those events.

Compared with the preserved policy, seed 102 improves final coverage from
**72.5654% at 12.43 s to 78.7418% at 16.00 s**; normalized AUC rises from
0.695217 to 0.701475. Seed 101's final coverage falls from **31.4379% at
13.26 s to 23.6438% at 16.00 s** despite resumed walking. Connected rooms also
loses coverage, as recorded above. This is an executable-progress correction,
not a claim of uniformly better coverage or readiness for allocator comparisons.

## Remaining uncertainty and response limits

| Corrected case | Peak planar body error A/B | Minimum sampled camera stand-off A/B |
| --- | --- | --- |
| Clutter 101 | 3.266 / 0.065 mm | 0.61236 / 0.61188 m |
| Clutter 102 | **89.816 / 3.307 mm** | 0.58245 / 0.67784 m |
| Connected rooms 101 | 3.154 / 2.107 mm | 1.70226 / 0.91900 m |

Stand-off is a diagnostic camera-XY distance to static axis-aligned reference
obstacles/walls at saved sensor times. It excludes other robots and the final
post-command state and is not continuous clearance certification. Clutter-102
A's larger pose error is a remaining **Issue #9** concern. These attempts do
not record full scan archives, so new accumulated-map/point-placement errors
are unavailable, not zero. Floor labels and true poses remain diagnostic-only.

A separate controlled physics unit probe turns for two seconds, then applies
three seconds of reverse command. Directed travel is +0.27844 m for
(-0.60, 0 yaw), +0.18622 m for (-0.57, +0.30 yaw), and **-0.05365 m** for
(-0.30, 0 yaw); all three have zero non-foot contacts. The log is
`reverse-response.log`. This demonstrates a motion-response limitation, not a
universal minimum productive speed. The longer live traces also show useful
progress during intervals containing slowed commands. An experimental blanket
restriction was tested separately and preserved at `d981cfb` in the isolated
worktree; it is **not merged into the validated main runtime**. Predictive
progress remains a nominal ranking heuristic, and measured progress remains
the authority for resetting the live blockage budget.

## Reproduction and acceptance

These commands name preserved attempts; choose new output directories when
repeating them:

```powershell
$env:OMP_NUM_THREADS = '1'
.venv/Scripts/python.exe -u scripts/validate_exploration.py --scenario cluttered_room --seed 101 --horizon 16 --output outputs/exploration-planning/executable-routes/clutter-s101-live-02
.venv/Scripts/python.exe -u scripts/validate_exploration.py --scenario cluttered_room --seed 102 --horizon 16 --output outputs/exploration-planning/executable-routes/clutter-s102-live-02
.venv/Scripts/python.exe -u scripts/validate_exploration.py --scenario connected_rooms --seed 101 --horizon 5 --output outputs/exploration-planning/executable-routes/connected-s101-live-02
```

Per-attempt `navigation-comparison.json` and `clearance-summary.json` retain
movement intervals, transitions, rejection reasons, directional travel, and
diagnostic errors. PowerShell wraps the expected no-progress warning on stderr
as `NativeCommandError` in the clutter logs; both episode results are valid,
both wrappers report `phase: complete`, and both verified videos are present.
No simulation or video export is missing from this six-attempt development set.

The frozen route fixture selects an executable alternative, physical fixtures
cover recovery followed by accepted walking and a stopped trap, existing retry
and horizon limits remain enforced, and fresh paired live evidence meets the
predeclared progress criterion in a formerly rejected case. The full main
regression suite passes. This completes the scoped executable-planning fix for
Issue #8 while retaining the stopped teammate, coverage regressions, pose error,
and nominal-response limitations above. Broader held-out/long-horizon readiness
remains Issue #11; no claim is made that all observed layouts are now solved.
