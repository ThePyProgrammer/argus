# Pose, floor, and map diagnosis — Issue #6

November 18, 2026. This follows the
[bounded recovery validation](exploration-bounded-recovery-validation.md).

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

## Development matrix

The matrix below is fixed before inspecting its fresh results. Every attempt
uses `scripts/validate_exploration.py`, a new output directory, and the corrected
gait/guard/recovery runtime. Runtime and instrumentation sources stay unchanged
through each simulation and video export. Start at most two attempts together.

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

Every completed attempt must report actual duration, coverage, pose/map/floor
errors, contact severity, falls, clearance rejections, recovery outcomes, and
its verified video. Early failure remains a failure; it is not evidence of
successful exploration or of the entire requested horizon. Generated artifacts
remain local. Issue #6 stays open while the matrix and analysis are incomplete.
