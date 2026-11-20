# Pose, floor, and map diagnosis — Issue #6

November 18–20, 2026. This follows the
[bounded recovery validation](exploration-bounded-recovery-validation.md).

The diagnostic scope is complete: frozen fixtures, separate reporting budgets,
six development attempts, seven verified videos including the unrecorded
control, and two exact full-episode recording comparisons. Registration accepts
every recorded update, but observation placement exceeds 50 mm in two cases.
The experiments separate pose-placement error from the floor band's removal of
low features; they do not resolve the remaining navigation failures or certify
an uncertainty allowance for the execution guard.

## Baseline observations

Offline scoring of the final #5 attempts gives the following peak errors.
These are measured errors on recorded trajectories, not certified bounds.

| Attempt / robot | Planar error | Vertical error | Attitude error | Missed floor / removed above 4 cm |
| --- | --- | --- | --- | --- |
| Clutter, A | 7.142 mm | 11.813 mm | 0.3519 degrees | 0 / 0 |
| Clutter, B | 0.0653 mm | 0.0275 mm | 0.00163 degrees | 0 / 0 |
| Connected rooms, A | 2.728 mm | 4.078 mm | 0.1578 degrees | 0 / 0 |
| Connected rooms, B | 0.807 mm | 0.758 mm | 0.0635 degrees | 0 / 0 |

No registration is rejected in these traces. This does not certify pose
accuracy. The old corridor/clutter errors in Issue #6 predate the corrected
gait and clearance/recovery policy; they must not substitute for current data.
The current clutter failure cannot simply be attributed to large pose drift or
missed floor samples. Its saved trace does not contain every accepted scan, so
it cannot independently establish accumulated-map error.

Reproduce this offline scoring with `scripts/replay_pose_map.py ATTEMPT --output
REPORT.json`. Without a scan archive it explicitly reports replay unavailable.
The initial reports are local under
`outputs/exploration-planning/pose-map-diagnosis/baseline-{clutter,connected}.json`.

An additional offline probe (`scripts/probe_terminal_clearance.py`) holds the
saved terminal observed grid fixed and constructs a stationary, settled guard
history, then substitutes estimated versus recorded true body pose. For A,
nearest occupied-cell-center distance changes from **1.036185 m** to
**1.042370 m**; both turn proposals change from rejection to acceptance. B's
distance changes from **0.964153 m** to **0.964155 m**, and all four recovery
proposals remain rejected. The planning radius stays **0.779205 m**.

This is decision sensitivity to millimetric pose changes near a threshold,
despite small overall pose error. It is not an exact reconstruction of live
velocity/gait history, a corrected historical map, or proof that an escape
would succeed. It supplies no true pose to live control and does not justify
weakening clearance. Preserve this distinction when interpreting the matrix.

The first 100 archived clutter-A scans were checked separately while the run
continued: zero mask disagreements, maximum retained-point placement error
**3.520 mm**, and fixed-lattice IoU **0.76865** for the estimated/filter branch.
The large voxel-label difference at small metric error illustrates sensitivity
to cell boundaries; it is not evidence of equally large physical displacement.
This partial check is exploratory and does not replace the complete replay.

## Controlled diagnostic replay

`scripts/validate_exploration.py --record-scans` records the original floor
filter's inputs and returned masks after that filter runs. It copies accepted
clouds, estimated and diagnostic true camera poses, timestamps, floor settings,
and map resolution into lossless checksummed chunks. Navigation never reads the
archive or diagnostic truth. Partial archives remain marked incomplete.

`scripts/replay_pose_map.py` compares four branches on those identical scans:

1. Estimated placement with an independent instance of the existing floor tracker.
2. Known placement with an independent instance of the same tracker.
3. Estimated placement with diagnostic floor labels.
4. Known placement with diagnostic floor labels, as the observed-surface reference.

Recorded masks must match the estimated replay. Both tracker branches apply the
existing acquisition/reacquisition cleanup to retained historical points. Map
comparison reports paired placement errors, nearest observed reference-surface
distances, retained true-floor points, and fixed-world voxel differences.
The common lattice avoids changes in a cloud-dependent voxel origin becoming
apparent pose error. It is a diagnostic discretization, not a replacement map.

These branches condition on accepted preprocessed scans. They do not rerun
registration, restore rejected or occluded observations, remove robot geometry,
or establish complete physical obstacle truth. Corresponding corrected points
are the reference for placement; |Z| <= 2 mm labels the flat fixture floor.
Points between 2 and 4 mm remain ambiguous, 4–40 mm features are counted
separately, and points above 40 mm are the raised-surface category.

Frozen analytical fixtures cover translation drift with correct floor labels,
historical placement error after the current pose recovers, and a narrow view
before/after broad floor acquisition. They preserve 6 cm obstacles while
exposing that 6 mm features fall inside the existing 15 mm floor band. This
limitation is reported, not hidden by changing the diagnostic labels or runtime
thresholds. The fixtures and their geometry are documented in
`tests/fixtures/pose_map_replay/README.md`.

## Reporting budgets

Before fresh attempts, the reporting comparison for planar pose and observation
placement is fixed at the existing **0.05 m planning margin**. Reports count
exceedances separately from tracking acceptance. This is an engineering
comparison, not a certified localization budget: pose and accumulated-map
errors can add, and the same margin cannot independently pay for both.

Floor settings remain **0.015 m inlier distance**, **0.04 m height tolerance**,
and the existing support/extent requirements. The diagnostic target is zero
removed samples above 4 cm. Small features inside the floor band have no
preservation guarantee. Report full distributions and observed maxima rather
than promoting passing these comparisons to a safety claim. No tracking,
floor, geometry, or guard thresholds are relaxed for this work.

Point samples and repeated frames are dependent observations. Their percentiles
describe this recorded stream, not independent trials or confidence bounds.

## Test evidence

The focused archive, replay, diagnostic-label, and video-workflow suite passes
**15 tests**, including exact commands/body-trace/coverage equality with scan
recording enabled versus disabled in a short real episode.

The expanded suite reports **1,083 passed, seven skipped, nine failed**
(`pose-map-diagnosis/regression-01.log`). Every failure is in the existing
subprocess-bridge tests using Unix `ipc:///tmp/...` addresses: this Windows
ZeroMQ build reports `zmq.has('ipc') == False`. Neither that implementation nor
its tests differs from the previous revision. This is retained as a platform
limitation, not silently counted as a passing full suite. The initial focused
test invocation also hit sandbox temporary-directory permissions; its fresh
rerun outside the sandbox passed.

The transport limitation is tracked independently in
[Issue #7](https://github.com/ThePyProgrammer/argus/issues/7), without machine
identifiers or hardware details.

## Development matrix

The matrix below is fixed before inspecting its fresh results. Every attempt
uses `scripts/validate_exploration.py`, a new output directory, and the corrected
gait/guard/recovery runtime. Runtime and instrumentation sources stay unchanged
through each simulation and video export. Start at most two attempts together.

For a fresh reproduction, choose an unused directory and the scenario/seed/
horizon from the matrix. For example (do not overwrite preserved attempts):

```powershell
$env:OMP_NUM_THREADS = '1'
.venv/Scripts/python.exe -u scripts/validate_exploration.py --scenario branching_corridor --seed 101 --horizon 8 --record-scans --output outputs/exploration-planning/pose-map-diagnosis/NEW-ATTEMPT
.venv/Scripts/python.exe scripts/replay_pose_map.py outputs/exploration-planning/pose-map-diagnosis/NEW-ATTEMPT --output outputs/exploration-planning/pose-map-diagnosis/NEW-ATTEMPT/pose-map-report.json
```

Replay is offline and must use the completed archive for full-episode claims.
The terminal pose-sensitivity probe is also offline:
`scripts/probe_terminal_clearance.py ATTEMPT --output REPORT.json`.

| Layout | Seed | Requested horizon |
| --- | --- | --- |
| Cluttered room | 101 | 16 s |
| Branching corridor | 101 | 8 s |
| Connected rooms | 101 | 8 s |
| Cluttered room | 102 | 16 s |
| Branching corridor | 102 | 10 s |
| Connected rooms | 102 | 10 s |

The clutter 101 attempt also compares all executed commands, body states, and
coverage against the uninstrumented #5 run ending at 13.26 seconds. The
connected-room 101 attempt compares its first five seconds with the saved
five-second baseline. A short real-episode unit fixture already checks exact
command, trajectory, and coverage equality with recording on versus off.

The separate eight-second unrecorded control is preserved in
`neutrality-connected-s101-h8-01`. This is
outside the fixed six-case characterization matrix and does not replace an
attempt. It strengthens neutrality evidence with a full-length comparison
containing continued navigation as well as a blocked teammate, alongside the
13.26-second clutter failure comparison. It uses the same wrapper and retains its
verified video; the only requested change was omission of `--record-scans`.

Every completed attempt must report actual duration, coverage, pose/map/floor
errors, contact severity, falls, clearance rejections, recovery outcomes, and
its verified video. Early failure remains a failure; it is not evidence of
successful exploration or of the entire requested horizon. Generated artifacts
remain local. Completion of this diagnostic matrix does not establish successful
exploration or remove the reported navigation failures.

## Completed attempts

| Attempt | Actual/requested time | Coverage | Outcome | Verified body samples |
| --- | --- | --- | --- | --- |
| [Clutter 101](../../outputs/exploration-planning/pose-map-diagnosis/scans-clutter-s101-h16-01/top-view.mp4) | 13.26/16 s | 31.4379% | `navigation_failed` | 1,327 |
| [Corridor 101](../../outputs/exploration-planning/pose-map-diagnosis/scans-corridor-s101-h8-01/top-view.mp4) | 8.00/8 s | 68.6756% | Horizon; recovery unresolved | 801 |
| [Connected rooms 101](../../outputs/exploration-planning/pose-map-diagnosis/scans-connected-s101-h8-01/top-view.mp4) | 8.00/8 s | 80.6442% | Horizon; A navigating, B blocked | 801 |
| [Clutter 102](../../outputs/exploration-planning/pose-map-diagnosis/scans-clutter-s102-h16-01/top-view.mp4) | 12.43/16 s | 72.5654% | `navigation_failed`; both retry budgets exhausted | 1,244 |
| [Corridor 102](../../outputs/exploration-planning/pose-map-diagnosis/scans-corridor-s102-h10-01/top-view.mp4) | 10.00/10 s | 15.9970% | Horizon; A failed, B has not reset blockage budget | 1,001 |
| [Connected rooms 102](../../outputs/exploration-planning/pose-map-diagnosis/scans-connected-s102-h10-01/top-view.mp4) | 10.00/10 s | 74.4732% | Horizon; A navigating, B recovering | 1,001 |
| [Unrecorded connected-room control, seed 101](../../outputs/exploration-planning/pose-map-diagnosis/neutrality-connected-s101-h8-01/top-view.mp4) | 8.00/8 s | 80.6442% | Horizon; exact recorded-run match | 801 |

Both attempts at `3dc52b6` retain unchanged source hashes, zero non-foot
contacts/falls, and zero verified body replay error. Clutter exactly matches all
1,327 command records (including terminal stop), body samples, and the complete
coverage result of `recovery/final-clutter-live-03`. This establishes recording
neutrality over the full 13.26-second failed episode. A makes two retreats and
exhausts its budget; B remains stopped with `no_safe_recovery`.

Corridor travels 1.01173 m as a team. At the horizon A is in its second recovery,
with a prior `no_progress` outcome; B has installed a route after one recovery,
but has not reset its blockage budget through resumed navigation progress.
Reaching eight seconds therefore does not establish successful escape or
sustained exploration. Full archived scan comparisons follow below.

Connected-room 101 at `f9a8e6b` also retains unchanged source hashes and zero
non-foot contacts/falls or body replay error. Its first 500 commands, 501 body
samples, and five-second coverage prefix exactly match the uninstrumented
five-second baseline. Team travel is 1.99782 m. B becomes blocked at 5.52 s
and has two replans but no recovery by the eight-second horizon, while A
continues navigating. The longer run exposes a limitation absent from the
shorter baseline. These attempts contain only expected foot-support contact
episodes; measured non-foot force and impulse are zero.

The clutter and corridor seed-102 attempts also retain unchanged sources, zero
non-foot contacts/falls, and zero video replay error. Clutter travels 1.37619 m;
both robots use four replans and two recovery attempts. A's last recovery is
rejected during execution; B's last recovery reports `no_progress`. Corridor
travels 0.86896 m; A reports `no_safe_recovery`, while B has installed a route
after two retreats but retains its blockage budget at the horizon. Their
minimum sampled camera clearances are 0.61942 m and 0.65408 m respectively.

Initial measured coverage differs by seed: clutter starts at 14.6569% / 37.7288%
for seeds 101 / 102, and corridor at 47.7679% / 0%. These are development cases
with different initial conditions, not paired evidence of an algorithmic
coverage improvement.

Connected-room 102 travels 2.75486 m. A remains in navigation; B blocks at
6.63 s, makes two replans, and remains in its first guarded recovery at the
ten-second horizon. Minimum sampled camera clearance is 0.67301 m. It records
zero non-foot contacts/falls, unchanged sources, and zero video replay error.

The unrecorded eight-second control exactly matches the recorded connected-room
101 attempt: **800 executed commands, 801 body states, and the complete coverage
result**. It also has zero non-foot contacts/falls and zero replay error. Together
with the complete 13.26-second clutter comparison and the short real-episode
fixture, this verifies command neutrality beyond five seconds in both a failed
episode and an episode with continued teammate navigation. Comparisons are
saved alongside the respective videos.

Across all six matrix attempts, every `src/` hash, exploration configuration,
gait configuration, recovery rule, execution geometry rule, and odometry rule
matches exactly (`runtime-consistency.json`). Each attempt's source hashes
remain unchanged. The commits differ only in diagnostic tooling/documentation;
no navigation, SLAM, floor, geometry, or guard settings changed across the matrix.

## Full clutter-101 replay

Both robots replay all 1,327 archived scan frames with **zero recorded-mask
disagreements**. Both have zero missed true-floor samples and zero removed
samples above 4 cm, in both estimated-pose and known-pose tracker branches.
No true-floor samples remain in either accumulated tracker map.

| Robot | Retained-point placement median / p95 / maximum | Maximum nearest reference-surface distance | Observations above 50 mm |
| --- | --- | --- | --- |
| A | 2.809 / 24.711 / 51.860 mm | 50.670 mm | 13,476 / 15,284,711 |
| B | 0.0252 / 0.0470 / 0.1417 mm | 0.1172 mm | 0 / 4,554,821 |

A therefore exceeds the fixed placement reporting threshold despite its
7.142 mm peak planar body error. Attitude and translation errors affect distant
observations differently from the body origin. Correcting floor labels alone
leaves the maximum placement error unchanged. Known-pose placement removes
paired pose-placement error by construction; it is not a live localization fix.

Of the samples between 4 and 40 mm above the diagnostic floor, the estimated
tracker removes 93,651 for A and 60,983 for B. The known-pose tracker removes
93,635 and 60,983 respectively. These include near-floor surface/wall-base
samples, not counts of distinct erased obstacles. Their persistence with known
poses separates the floor-band limitation from pose drift. With known poses,
the floor tracker leaves 11 fewer fixed-grid cells for A than diagnostic floor
labels; B's occupied-cell set is unchanged.

Estimated-map fixed-grid IoU is 0.77474 for A and 0.75610 for B. In particular,
B's submillimetric metric error with that voxel IoU reinforces that cell-label
overlap alone is a poor measure of physical displacement. Complete per-frame
and four-branch map results are saved in the attempt's `pose-map-report.json`.

## Full corridor-101 replay

Both robots replay all 800 accepted scan frames with zero recorded-mask
disagreements. Estimated-pose and known-pose branches both report zero missed
floor samples and zero removed samples above 4 cm; neither tracker map retains
true-floor samples.

| Robot | Peak planar / vertical / attitude error | Retained-point placement p95 / maximum | Observations above 50 mm |
| --- | --- | --- | --- |
| A | 21.932 mm / 3.480 mm / 0.1628 degrees | 21.702 / 22.096 mm | 0 / 1,671,131 |
| B | 1.997 mm / 2.850 mm / 0.0929 degrees | 8.377 / 9.609 mm | 0 / 16,530,960 |

B's maximum over all input points, before filtering, is 9.622 mm. For A,
774 of 799 post-initialization registrations have observable rank five; the
other 25 have rank six. All are accepted, with minimum post-seed fitness
0.9355. This is consistent with weaker geometric constraints, but rank alone
does not prove which errors caused the accumulated drift. B has rank six in
all 799 post-seed registrations. Clutter-101 has rank six for both robots in
all 1,326 post-seed registrations, yet A exceeds the point-placement threshold.
Neither acceptance nor numerical rank is a pose-accuracy certificate.

The estimated tracker removes 29,119 / 90,588 samples in the 4–40 mm band for
A / B; known-pose tracking removes 29,113 / 90,568. Known-pose tracker occupancy
matches the diagnostic floor-label map for A and lacks five fixed-grid cells
for B. Estimated-map IoU is 0.53295 / 0.74518, with maximum nearest reference
surface distance 21.667 / 8.568 mm. Metric distance and cell overlap again
answer different questions.

The minimum sampled camera-to-static-obstacle distance is 0.56484 m in
clutter-101 and 0.65785 m in corridor-101. These compare the diagnostic true
camera point with static axis-aligned walls/obstacles at saved sensor times;
they exclude other robots and are not continuous articulated-body guarantees.
Clutter B has 100 initial stopping-envelope rejections; corridor A has 13.
Clean physical contact counts do not erase those modeled clearance failures.

## Full connected-room-101 replay

Both 800-frame archives have zero recorded-mask disagreements, missed floor
samples, removed samples above 4 cm, and retained true-floor samples. The
maximum planar errors are 3.188 mm for A and 0.807 mm for B; maximum observation
placement errors are 25.662 mm and 6.229 mm. Neither robot exceeds the 50 mm
reporting threshold. Retained-point placement p95 is 18.165 mm / 4.121 mm,
while maximum nearest reference-surface distance is 21.998 mm / 6.012 mm.

Estimated tracking removes 88,916 / 71,341 samples in the 4–40 mm band;
known-pose tracking removes 88,883 / 71,279. Fixed-grid IoU is 0.47991 / 0.51806,
again much more sensitive to cell boundaries than the metric displacement.
The minimum sampled camera-to-static-obstacle distance is 0.71833 m.

## Full clutter/corridor-102 replays

All four robot archives reproduce their recorded masks exactly. Each has zero
missed true-floor samples, zero removed samples above 4 cm, zero retained
true-floor samples, and zero observations above the fixed 50 mm placement
comparison. Registration remains accepted throughout.

| Layout / robot | Peak planar error | Maximum input-point placement error | Retained placement p95 | Maximum nearest reference-surface distance |
| --- | --- | --- | --- | --- |
| Clutter A | 2.385 mm | 8.850 mm | 6.804 mm | 7.780 mm |
| Clutter B | 1.389 mm | 5.806 mm | 3.555 mm | 4.688 mm |
| Corridor A | 16.433 mm | 16.435 mm | 6.661 mm | 10.199 mm |
| Corridor B | 11.188 mm | 11.541 mm | 10.903 mm | 11.493 mm |

Clutter A/B contain 15,093,809 / 22,787,807 input points; corridor A/B contain
3,145,571 / 9,303,438. Estimated-pose tracker removals in the 4–40 mm band are
97,293 / 135,576 for clutter and 15,468 / 63,635 for corridor. Known-pose
removals are 97,215 / 135,462 and 15,465 / 63,637 respectively. Known-pose
tracker maps omit 6 / 9 fixed-grid cells in clutter and 3 / 3 in corridor
relative to the diagnostic floor-label maps, with no extra cells.

Estimated-map fixed-grid IoUs are 0.75866 / 0.79354 in clutter and
0.62848 / 0.37701 in corridor. These do not override the metric-distance
measurements or establish physical obstacle removal. The samples are repeated
observations, not independent trials.

## Full connected-room-102 replay

Both 1,000-frame archives reproduce their recorded masks exactly. Estimated-
and known-pose trackers have zero missed floor samples, zero removed samples
above 4 cm, and zero retained true-floor samples. All registrations are accepted.

| Robot | Peak planar / vertical / attitude error | Maximum input-point placement error | Retained placement p95 | Observations above 50 mm |
| --- | --- | --- | --- | --- |
| A | 5.780 mm / 8.228 mm / 0.3461 degrees | 50.269 mm | 22.619 mm | 108 / 18,244,515 |
| B | 7.912 mm / 0.819 mm / 0.0411 degrees | 7.906 mm | 5.187 mm | 0 / 8,265,996 |

A supplies a second case where small planar body error and accepted tracking
coexist with observation placement beyond the fixed reporting comparison.
Correcting floor labels alone leaves its maximum placement error unchanged.
Maximum nearest reference-surface distances are 43.594 / 5.682 mm, and
estimated-map fixed-grid IoUs are 0.49914 / 0.54847 for A / B.

Estimated tracking removes 107,035 / 70,492 samples in the 4–40 mm band;
known-pose tracking removes 107,021 / 70,499. Each known-pose tracker map omits
16 fixed-grid cells relative to diagnostic floor labels and adds none. These
are repeated near-floor observations, not distinct missing-obstacle counts.

## Acceptance and remaining limits

The three Issue #6 acceptance items are supported by:

- Frozen analytical pose, historical-map, narrow-floor, and low-feature
  fixtures, plus independent estimated/known-pose replay on all six complete
  live scan archives. All recorded floor masks match their replay exactly.
- Fixed 50 mm pose/placement comparisons and a zero-removal target above
  4 cm, reported independently of registration acceptance. No live thresholds
  changed. Across 142,690,726 input-point observations, 13,584 exceed 50 mm:
  13,476 in clutter-101 A and 108 in connected-room-102 A. Peak planar body
  error is 21.932 mm; peak observation-placement error is 51.860 mm.
- Corrected-gait runs across three layouts and two development seeds, with
  actual durations from 8.00 to 13.26 seconds, preserved failures, contact
  severity, clearance and recovery outcomes, and verified videos. Complete
  8.00-second and 13.26-second comparisons preserve commands, body states,
  and coverage exactly with recording enabled versus disabled.

All six live replays have zero missed diagnostic floor samples, zero removed
samples above 4 cm, and zero retained true-floor samples in both tracker
branches. That does not guarantee preservation of low features within the
existing floor band. The frozen 6 mm fixture and the live known-pose removals
make this limitation explicit.

This is a bounded development characterization on flat-floor scenes and
accepted, preprocessed observations. Two seeds and these durations do not
establish long-horizon robustness, unseen-obstacle completeness, or a certified
pose/map error bound. Fixed-grid overlap is not physical displacement; the
planning margin cannot independently absorb both pose and map error. No live
SLAM, floor-filter, navigation, geometry, or guard correction is claimed.

Both clutter attempts still terminate with navigation failure. Other attempts
reach their horizons with blocked, failed, or recovering teammates. Their
zero non-foot contact force/impulse and zero falls do not establish exploration
success. The IPC failures remain separately open under Issue #7. Local
`matrix-summary.json`, `runtime-consistency.json`, and `completion-audit.json`
under `outputs/exploration-planning/pose-map-diagnosis/` summarize the completed
evidence; the per-attempt archives and reports retain the underlying data.
