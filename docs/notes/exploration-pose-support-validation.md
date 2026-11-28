# ICP pose-chain support — scoped Issue #9 fix

November 26–27, 2026. This follows the
[executable-route validation](exploration-executable-routes-validation.md).

## Frozen scope and acceptance criteria

The preserved clutter-102 route attempt reaches 89.816 mm peak planar error
for A while raw registration remains accepted. Its alignment rank falls from
six to five before the large error. Registration acceptance is therefore not
sufficient evidence for navigation or continued global-map insertion.

`icp_observability_chain_v1` adds a necessary numerical support check. It is
**not a pose accuracy bound**, calibrated covariance, or complete resolution
of Issue #9. The existing solver's six-direction rank threshold is unchanged.
Full-rank drift, accumulated placement error, and range-dependent effects of
attitude uncertainty still require a calibrated uncertainty treatment.

The backend publishes `pose_map_support` separately from `accepted` and raw
tracking status. States are `seeded`, `observable`, `unavailable`, `invalid`,
`unobservable_motion`, and `unobservable_history`. Rank is a dimensionless
integer; observation and first-loss times are simulation seconds. Translation,
attitude, and historical-map bounds are explicitly unavailable (`null`), with
field names specifying metres and radians. Freshness uses the existing
`motion_observation_max_age_s`; no clearance radius or margin changes.

The explicit initial pose permits the first map seed. Accepted relative motion
with fewer than six supported directions permanently invalidates the chain.
A later full-rank relative alignment cannot restore the missing history.
Rejected registration retains the old reference and can recover through a
later supported match. Missing, malformed, or stale support blocks motion and
map insertion. The consumer retains history loss across backend resets and new
waypoint targets: restart localization and the map together to recover.

Only ICP currently declares this contract. Other backends retain their existing
behavior and are outside this fix. Raw ICP diagnostics remain available after
support loss; new points are withheld from both its global cloud and the
exploration occupancy/floor pipeline. The execution guard issues a stop, and
navigation reports `pose_history_unobservable`. An unaffected teammate may
continue. Ground truth remains diagnostic-only.

Before fresh live outcomes, acceptance is fixed as follows:

- Analytical wall-parallel motion must remain accepted by raw registration
  while failing numerical support, with no subsequent map insertion. A later
  full-rank increment must not repair the history. Missing/stale support and
  backend-only reset must not bypass the navigation consumer.
- Reproduce cluttered_room seed 102 for a 16-second requested horizon, with
  scan recording. Compare against preserved `executable-routes/clutter-s102-live-02`:
  commands must match until the first unsupported update, then the affected
  robot must stop and withhold scans. Report actual duration, coverage cost,
  contacts, falls, and pose/retained-map diagnostics, including residual errors.
- Run connected_rooms seed 101 for 5 seconds and cluttered_room seed 101 for
  16 seconds as regression cases. These are previously seen development cases,
  **not held-out accuracy calibration**. Report any conservative stop explicitly.
- Preserve every attempt and its verified top-view video, including early
  navigation failures. No parameter retuning between these attempts.

The complete uncertainty budget and broader held-out/long-horizon evaluation
remain open under Issues #9 and #11 respectively.

## Regression evidence

Runtime implementation: `f08ef27`. The existing focused SLAM, motion-clearance,
and bounded-recovery suite passes **47 tests**. The new pose-support suites
pass **22 tests**, including an analytically rendered wall-parallel slide:
raw registration accepts rank three with fitness above 0.99 while missing
over 0.19 m of translation. The backend withholds its scan and freezes the
global cloud, even across subsequent full-rank increments and the periodic
downsampling boundary. Integration tests exercise missing/stale evidence,
per-robot independence, and attempted recovery via backend reset/new target.

The broad exploration/control/coordination/bridge/locomotion/SLAM run reports
**1,132 passed, 9 skipped, 2 failed** (`regression-01.log`, 3,143.69 s).
Both failures were outdated test expectations: the capability dictionary lacked
the new contract, and the corridor observer-neutrality test assumed both robots
reached planning. In that fixture, one robot now correctly stops on unsupported
history before planning. Its observed and unobserved command/body traces still
match exactly. The corrected test asserts the persistent stop and zero commands,
while requiring actual route previews for its supported teammate.

The follow-up runs both corrected tests plus ICP backend, pose-support consumer,
and bounded-recovery tests: **31 passed in 106.20 s**
(`regression-followup-01.log`). Thus all 1,134 non-skipped cases from the broad
selection have passing evidence across the broad and focused runs; this is not
a claim that the original broad invocation was green. Artifacts are under
`outputs/exploration-planning/pose-support/`.

## Fresh live outcomes

All three attempts used runtime `f08ef27`, `OMP_NUM_THREADS=1`, scan recording,
and the frozen parameters above. Their source manifests report unchanged source
files. Each wrapper reports `complete`, and its video metadata matches the
diagnosis hash, measured duration, and coverage. Body replay checks cover 1,601
states per clutter attempt and 501 for connected rooms. No attempt or video is
missing. All three have zero falls and zero non-foot contact episodes.

| Attempt / verified video | Actual / requested time | Initial / final coverage | Paired result |
| --- | --- | --- | --- |
| [Clutter 102](../../outputs/exploration-planning/pose-support/clutter-s102-live-01/top-view.mp4) | 16.00 / 16 s | 37.7288 / 78.7418% | A stops at first rank loss; B continues; final coverage unchanged |
| [Clutter 101](../../outputs/exploration-planning/pose-support/clutter-s101-live-01/top-view.mp4) | 16.00 / 16 s | 14.6569 / 23.6438% | All 1,600 command intervals and complete body trajectory exactly match baseline |
| [Connected rooms 101](../../outputs/exploration-planning/pose-support/connected-s101-live-01/top-view.mp4) | 5.00 / 5 s | 58.2179 / 71.5081% | All 500 command intervals and complete body trajectory exactly match baseline |

Clutter-102 A first loses a direction at **11.44 s**, at **6.370 mm** planar
error. Its peak error before that loss is **7.615 mm**. All 1,144 preceding
command intervals match the preserved attempt exactly. The same update issues
`failed: pose_history_unobservable`; every subsequent command is zero. The
archive contains 1,144 A scans, ending at **11.43 s**, and **none at or after
the support loss**. Raw registration remains accepted, demonstrating why its
status cannot replace the separate support check.

The stopped robot continues sensing for diagnostics. Its estimate still drifts:
peak planar error is **39.695 mm**, versus **89.816 mm** in the preserved
attempt. This is an observed reduction, not evidence that localization recovered
or that 39.695 mm is a bound. The unsupported estimate never resumes map updates
or navigation. B's entire command and body trajectory match baseline exactly;
it contributes all 1,600 scans and reaches the horizon. Team coverage remains
**78.7418%**, so this specific stop has no measured final coverage cost.
Zero commands do not mean instantaneous physical immobility: A's maximum
sampled planar displacement from its body position at 11.44 s is **72.886 mm**
after the stop (70.447 mm at the final state). No non-foot contact or fall is
recorded during that residual motion. These are trace measurements, not a
general stopping-distance guarantee.

Neither regression attempt loses rank after its seed. Clutter-101 retains the
earlier B `no_safe_recovery` failure while A continues; the new check does not
solve that geometric blockage. Its unchanged 23.6438% final coverage and the
connected case's unchanged 71.5081% are regressions relative to some older
policies, as documented in the route report, not improvements from this fix.

Reproduce with new output directories:

```powershell
$env:OMP_NUM_THREADS = '1'
.venv/Scripts/python.exe -u scripts/validate_exploration.py --scenario cluttered_room --seed 102 --horizon 16 --record-scans --output outputs/exploration-planning/pose-support/clutter-s102-live-01
.venv/Scripts/python.exe -u scripts/validate_exploration.py --scenario cluttered_room --seed 101 --horizon 16 --record-scans --output outputs/exploration-planning/pose-support/clutter-s101-live-01
.venv/Scripts/python.exe -u scripts/validate_exploration.py --scenario connected_rooms --seed 101 --horizon 5 --record-scans --output outputs/exploration-planning/pose-support/connected-s101-live-01
```

The named directories above are preserved and cannot be reused by the wrapper.
Per-attempt `pose-support-summary.json` records command comparisons, rank-loss
times, scan counts, pose errors, and video verification. Comparison baselines
are the corresponding `executable-routes/*-live-02` attempts. Diagnostic truth
is used only for these comparisons, never to select the live stop.
