# Bounded replanning and recovery — Issue #5

Validation November 15–16, 2026; final evidence review November 18. This continues the
[restart and stopping validation](exploration-restart-settling-validation.md).
The old clutter baseline completed 10 seconds with 31.2745% coverage but issued
1,654 candidate selections: execution rejection cleared the route, the missing
route triggered another scan on the next frame, and zero accepted motion kept
the commanded-progress detector from triggering recovery. Successful A* search
was repeatedly mistaken for a usable route.

## Runtime changes

`93e851d` adds an observed-space route option and explicit blocked-start
classification. Exploration uses that option in `c4c2968`: unknown center cells
are excluded from reachability, A*, and smoothing, matching the guard. The
generic planner retains its optional unknown-space mode. This removes one
planner/execution mismatch; static geometry still does not certify the dynamic
stopping envelope.

`c4c2968` adds a per-robot state machine shared by single-robot, coordinated,
and evaluation execution. States distinguish `navigating`, `blocked`,
`replanning`, `recovering`, `exhausted`, and `failed`. The same bounded policy
handles blocked planning starts, unreachable routes, execution rejection,
and accepted motion without estimated progress.

The initial implementation uses four replans, two recovery attempts, 32 A* candidates
per scan, and twelve simulated seconds per unresolved blockage. Each blocked
interval waits at least one second for settling while sensing continues. After
two unsuccessful replans, recovery previews reverse at 0.20 m/s, turns at
0.50 rad/s in either direction, and forward at 0.20 m/s. A second attempt prefers
a turn. The physical validation below increases the reverse proposal to 0.60 m/s;
the retry-scheduling and progress refinements are also recorded below.
Every preview uses an isolated copy of the existing guard history.
Every executed command, including subsequent recovery frames, passes the real
guard again with current observations and unchanged calibration.

Recovery requires 0.10 m estimated translation or 0.35 rad estimated rotation
within 1.5 seconds. Otherwise it reports `no_progress`. Any execution rejection
immediately stops and invalidates that recovery. After settling, a bounded
replan can use the resulting observations. Only 0.15 m translation while
following an installed navigation route resets the blockage budget. Installing
a route, turning, or completing a recovery primitive alone does not count as
resumed exploration.

No admissible primitive produces `failed: no_safe_recovery`, retaining the
individual clearance reasons. The retry limit and deadline have separate
failure reasons. Failure remains stopped until an explicit target resets the
policy. It does not automatically revive on map growth or a teammate's progress.
The teammate keeps its own independent state and continues. If all active robots
terminate and any has failed navigation, the episode records `navigation_failed`
with its actual end time. It does not label that outcome frontier exhaustion.

Here, a trap means no admitted escape under the observed map, existing guard,
and finite motion choices. It is not proof of physical entrapment or that every
possible maneuver has been searched. No obstacle is erased, no robot dimension
or stopping allowance is reduced, and no clearance check is bypassed. Pose/map
uncertainty and wider dynamics/generalization remain #6 concerns.

## Focused evidence

Fixtures exercise the real guard with estimated poses and deliberately incorrect
simulator truth poses. They cover:

- An inflated start beside a wall: all commands remain zero, retries stop, and
  the result records `no_safe_recovery` and candidate clearance reasons.
- A start with no observed passable neighbors: fresh observations of previously
  unknown free space restore a checked route during the retry window. No
  obstacle deletion or assumed map error is involved.
- Persistent execution rejection despite successful route search: bounded
  replanning ends explicitly instead of retrying every frame.
- A checked retreat followed by successful replanning and observed navigation
  progress, and the same accepted recovery with no pose progress, which fails.
- An obstacle observed during recovery: the next frame stops the primitive.
- Preview isolation: trying multiple candidates does not consume pose, gait,
  or settling history on the real guard.
- Independent teammate progress, shared physics time during recovery, deadline
  accounting, and a navigation failure that still produces a valid episode
  result and follows the video-export workflow.

The recovery fixtures establish policy behavior and guarded commands, not a
claim that every blocked layout is recoverable. Live outcomes are recorded
separately below.

The initial affected suite passes **958 tests with seven skips** at runtime
`c4c2968` (validation revision `dc0f852`, which changes only a test fixture).
It includes exploration, control and physical stopping fixtures, coordination,
bridge, coverage metrics, and the selected gait/locomotion suites:

```powershell
$env:OMP_NUM_THREADS = '1'
.venv/Scripts/python.exe -u -m pytest tests/exploration tests/control tests/coordination tests/bridge tests/metrics/test_exploration_coverage.py tests/locomotion/test_gait_controller.py tests/locomotion/test_gait_clearance.py tests/locomotion/test_gait_transitions.py tests/locomotion/test_locomotion.py -q -p no:cacheprovider --basetemp outputs/exploration-planning/recovery/test-tmp-regression-03
```

The first broad run could not access pytest temporary directories inside the
Windows sandbox and failed in cleanup. The next run passed 955 tests with seven
skips but exposed one coordinator fixture that supplied a `MagicMock` instead
of grid geometry. `dc0f852` supplies a real free grid; its 17 coordinator checks
pass, and the final suite above includes that correction and the last two
acceptance cases. An earlier episode fixture caught and corrected the missing
`navigation_failed` value in the coverage termination contract before any live
attempt. Logs remain under `outputs/exploration-planning/recovery/`.

## Reproduction

Always choose a new output directory; the commands below name the preserved
attempts and must not be rerun over them.

```powershell
$env:OMP_NUM_THREADS = '1'
.venv/Scripts/python.exe -u scripts/validate_exploration.py --scenario cluttered_room --seed 101 --horizon 10 --output outputs/exploration-planning/recovery/bounded-clutter-live-01
.venv/Scripts/python.exe -u scripts/validate_exploration.py --scenario connected_rooms --seed 101 --horizon 5 --output outputs/exploration-planning/recovery/bounded-connected-live-01
.venv/Scripts/python.exe -u scripts/validate_exploration.py --scenario cluttered_room --seed 101 --horizon 16 --output outputs/exploration-planning/recovery/bounded-clutter-live-02
```

## Initial live evidence at `dc0f852`

Both completed attempts retain unchanged runtime source hashes and zero
non-foot contact episodes or falls:

| Attempt | Actual/requested time | Coverage | Team travel | Verified body states |
| --- | --- | --- | --- | --- |
| [Clutter](../../outputs/exploration-planning/recovery/bounded-clutter-live-01/top-view.mp4) | 10.00/10.00 s | 31.2745% | 0.62231 m | 1,001, zero replay error |
| [Connected rooms](../../outputs/exploration-planning/recovery/bounded-connected-live-01/top-view.mp4) | 5.00/5.00 s | 77.1523% | 1.37630 m | 501, zero replay error |

Connected rooms exactly preserves all 500 executed commands, 501 body samples,
and every coverage sample from `settling-connected-live-01`. Both robots remain
in navigation and issue nonzero commands at 4.99 seconds. There are no recovery
entries or execution rejections. The comparison is saved alongside the video.

Clutter reduces candidate selection from **1,654 to 13 calls**. B stops with
`no_safe_recovery` at 3.03 seconds after two replans; all four candidate motions
fail obstacle clearance. It never receives a moving command. A continues
independently, first blocks at 3.23 seconds, and attempts a guarded reverse from
6.25 through 7.74 seconds. At 7.75 seconds the attempt reports `no_progress`:
net estimated displacement during the primitive is only **3.646 mm**, well
below the 0.10 m threshold. It retries twice more and remains blocked at the
10-second horizon. The extra travel includes gait and settling motion; coverage
does not improve. This is **not successful escape or sustained exploration**.

A also has 85 rejected stopping-envelope checks during this run, while B has
100 initial stopping rejections. A zero command cannot restore an already
rejected modeled tail. Clean contacts do not certify continuous clearance;
the existing map/model uncertainty limits remain. Complete state transitions,
guard counts, and recovery durations are in each `navigation-summary.json`.

## Physical retreat correction

The first live attempt exposed a poor primitive choice. A separate known-map
physics probe commands each primitive for 1.5 seconds with exact test poses:
reverse at -0.20 m/s moves about **+1.64 cm** in X, while -0.40, -0.60, and
-0.80 m/s produce approximately **-8.77, -19.76, and -30.56 cm** respectively.
The three stronger reverse probes have zero non-foot contacts. Forward at
0.20 m/s and turns at +/-0.50 rad/s can achieve their progress thresholds in
the open-space probe. Command magnitude is not measured body speed.

`050e308` changes the default reverse proposal to **-0.60 m/s**, retaining the
same guard, scaling options, geometry, stopping envelope, timeout, and progress
threshold. It also requires progress in the commanded longitudinal or yaw
direction; lateral drift or opposite motion cannot qualify. No gait parameters
are changed. The correction was prepared in an isolated checkout while the
earlier live attempt retained unchanged runtime files; its 25 Go2 asset files
match the main checkout exactly.

The first physical fixture reproduces the inadequate retreat with the old
default. With the correction it achieves the directed retreat threshold, but
its original navigation-progress assertion could count body drift during a
turn. That limitation is corrected below. The true-trap fixture remains
stopped with an explicit reason. These fixtures use real gait/physics, known
maps, exact test pose oracles, and physics-step contact accounting. They are
controlled unit fixtures, not a replacement for live SLAM validation.

## Checking the route after the last recovery

The initial retry schedule could spend all four replans before its second
recovery, leaving no route check afterward. A focused fixture reproduces this.
`d8582d7` reserves a replan after each permitted recovery within the same four
replan/two recovery limits. Smaller custom replan budgets reduce the permitted
recovery count rather than issuing a maneuver that cannot receive a route check.

The extended attempts preserve this sequence, with zero non-foot contacts,
zero falls, unchanged runtime source hashes, and zero body replay error:

| Attempt | Runtime | Actual/requested time | Coverage | Outcome | Verified body states |
| --- | --- | --- | --- | --- | --- |
| [Original policy, extended](../../outputs/exploration-planning/recovery/bounded-clutter-live-02/top-view.mp4) | `dc0f852` | 10.77/16.00 s | 31.2745% | Both robots fail `no_safe_recovery` | 1,078 |
| [Directed retreat](../../outputs/exploration-planning/recovery/directed-clutter-live-01/top-view.mp4) | `050e308` | 12.76/16.00 s | 31.2908% | A retreats twice but exhausts replans before checking its last recovery | 1,277 |
| [Extra old-policy comparison](../../outputs/exploration-planning/recovery/final-clutter-live-01/top-view.mp4) | `dc0f852` | 10.77/16.00 s | 31.2745% | Extra old-revision attempt; not final-policy evidence | 1,078 |
| [Reserved route checks](../../outputs/exploration-planning/recovery/final-clutter-live-02/top-view.mp4) | `d8582d7` | 13.26/16.00 s | 31.4379% | Both recoveries receive replans; A then exhausts its budget | 1,327 |

All four end with `navigation_failed`, not frontier exhaustion or a full
16-second horizon. The extended original-policy run exactly preserves the
first 1,000 commands, 1,001 body states, and coverage samples of the ten-second
attempt. The extra comparison started when a checkout check detected CRLF/LF
differences between otherwise-identical test copies and prevented a merge; the
following launch incorrectly proceeded on the older revision. It was preserved
and verified, and is explicitly excluded from final-policy acceptance.

At `d8582d7`, B fails at 3.03 seconds with no safe recovery candidate. A makes
two directed retreats (6.25–7.18 s and 9.82–10.73 s), then receives a route check
after each. Its intervening navigation commands are turns, not accepted walking.
The final execution rejection is at 12.26 seconds, followed by
`retry_budget_exhausted` at 13.26 seconds. There are **14 candidate-selection
calls**, zero failed A* searches, and **0.93561 m** total team travel. A has no
rejected stopping envelopes in this run; B retains its 100 initial stopping
rejections. The small coverage gain is not sustained exploration success.

The affected suite at `d8582d7` passes **967 tests with seven skips**. A separate
test launch during the failed checkout still used the old runtime with newer
fixtures and produced five expected failures; `regression-04.log` is not a
final-revision result. The verified revision's suite is `regression-05.log`.

## Requiring accepted translation for navigation progress

`102f9c8` excludes body drift during turning or standing from the navigation
progress threshold. Only observed net displacement during accepted translation
commands can reset the blockage budget. An idle or pure-turn interval resets
the position anchor, so its drift cannot be credited to a later walking command.
Provenance records `bounded_commanded_replanning_v4`.

The strengthened physical fixtures distinguish an escape to a newly visible
lateral frontier, a stopped trap, and a long turn that must hit the blockage
deadline. Scripted frontier visibility depends on the physical test pose,
independently of the policy's success label. The escape requires both a directed
retreat and actual commanded walking progress. The long-turn case correctly
fails with `blocked_timeout` instead of using turning drift to reset its budget.
All three have zero non-foot contacts. Together with the policy and retry-budget
fixtures, **22 tests pass**. The prior clutter trace contains 115 post-block
navigation ticks and zero accepted translation ticks; its turns are not evidence
of resumed walking.

The complete affected suite at `102f9c8` passes **969 tests with seven skips**
in 446.74 seconds (`regression-06.log`). It uses the same suite selection above
with a fresh `test-tmp-regression-06` temporary directory. This is the final
runtime's regression result; earlier mixed-revision or sandbox failures are
retained separately.

## Final live validation at `102f9c8`

The final attempts use the same wrapper in fresh directories, with runtime
sources held unchanged for their complete simulations and video exports:

```powershell
$env:OMP_NUM_THREADS = '1'
.venv/Scripts/python.exe -u scripts/validate_exploration.py --scenario cluttered_room --seed 101 --horizon 16 --output outputs/exploration-planning/recovery/final-clutter-live-03
.venv/Scripts/python.exe -u scripts/validate_exploration.py --scenario connected_rooms --seed 101 --horizon 5 --output outputs/exploration-planning/recovery/final-connected-live-01
```

| Attempt | Actual/requested time | Coverage | Outcome | Verified body states |
| --- | --- | --- | --- | --- |
| [Clutter](../../outputs/exploration-planning/recovery/final-clutter-live-03/top-view.mp4) | 13.26/16.00 s | 31.4379% | `navigation_failed`; bounded retries exhausted | 1,327, zero replay error |
| [Connected rooms](../../outputs/exploration-planning/recovery/final-connected-live-01/top-view.mp4) | 5.00/5.00 s | 77.1523% | Horizon; both robots navigating | 501, zero replay error |

Clutter records zero non-foot contacts or falls and **0.93561 m** team travel.
B remains stopped and reports `no_safe_recovery` at **3.03 s**: every proposed
primitive fails the existing guard. A continues independently, completes
directed guarded retreats at **7.18 s** and **10.73 s**, and receives a route
check after each. It uses four replans and two recovery attempts before reporting
`retry_budget_exhausted` at **13.26 s**. Its final moving command is at 12.25 s.
The episode ends explicitly with `navigation_failed`, not completion of the
16-second horizon or frontier exhaustion.

There are **14 candidate-selection calls**, versus 1,654 in the original
ten-second baseline. Successful A* searches still encounter execution rejection;
the bounded policy handles that mismatch without silently retrying forever.
Neither retreat produces resumed walking along a navigation route. A has no
rejected stopping envelopes; B retains 100 initial stopping-envelope rejections.
The slight coverage gain does **not** establish sustained exploration or a
continuous-time clearance certificate.

All 1,327 command records (including the terminal stop), 1,327 body samples,
and the complete coverage result exactly match `final-clutter-live-02` at
`d8582d7`. The stricter accepted-translation progress rule therefore preserves
this live outcome while fixing the false progress exposed by the physical
long-turn fixture. The comparison is saved in `baseline-comparison.json`.
Runtime hashes remain unchanged; video verification reports zero body replay
error and the wrapper records `phase: complete`. The video's time axis spans
the actual 13.26-second episode; the requested horizon remains 16 seconds.

Connected rooms has zero recoveries, execution rejections, non-foot contacts,
or falls, and 1.37630 m team travel. All 500 executed commands, 501 body states,
and the complete coverage result match `bounded-connected-live-01` exactly
(`baseline-comparison.json`). Runtime source hashes remain unchanged, and the
wrapper records `phase: complete` after verification and video export.

## Acceptance coverage and limits

- Recoverable blocked starts and stopped traps are covered by
  `test_blocked_start_can_replan_after_fresh_free_space_observations` and
  `test_true_trap_stays_stopped_and_finishes_with_reason`. The physical
  `escape`, `trap`, and `long_turn` cases additionally distinguish walking
  after retreat, no admitted escape, and expiration without resumed walking.
- `test_repeated_execution_rejection_has_bounded_planning` covers repeated
  successful route search followed by execution rejection. The retry-budget
  fixtures reserve a route check after every permitted recovery, including
  reduced custom budgets.
- `test_recovery_rechecks_changed_obstacles_and_never_reuses_preview` checks
  the actual guard on subsequent recovery frames. The deadline fixture counts
  waiting and recovery time; evaluation continues stepping the shared physics
  clock through these states.
- `test_failed_robot_does_not_stop_productive_teammate` covers independence.
  The clutter trace also keeps A active after B's explicit failure.
- Both final live attempts preserve diagnostics, actual duration, coverage,
  recovery outcomes, contact measurements, and verified videos. Earlier failed
  attempts and superseded revisions remain available in the tables above.

Together, the focused fixtures, full affected regression suite, and fresh live
evidence meet Issue #5's bounded replanning/recovery acceptance criteria.

These are bounded development-policy guarantees under the existing estimated
pose, observed occupancy, calibration, and clearance model. They do not certify
every physical escape, eliminate pose/map uncertainty, or establish sustained
clutter exploration. No robot dimensions, obstacle observations, or guard checks
were relaxed. Issue #6 remains open for its separate uncertainty and broader
validation work. Generated traces and videos remain local; they are not uploaded
to GitHub.
