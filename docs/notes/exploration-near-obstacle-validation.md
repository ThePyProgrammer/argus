# Close-range tracking correction

Dense depth observations near a wall were losing too much detail during fixed-resolution downsampling. The estimator could reject a valid observation because fewer than 100 surface correspondences remained. Registration now retains finer observed points when necessary; map density and alignment acceptance requirements stay unchanged.

Correction revision: `f974c06`.

## Correction

Start with the existing map cloud. If fewer than 200 planar samples remain, retry registration preparation from the original observation at half the voxel size, up to three times. At the default 3 cm resolution, the finest registration grid is 3.75 mm. The extra support margin allows some correspondence loss while retaining the same 100-match requirement.

The process does not interpolate or duplicate points. Sparse observations and line-shaped geometry still fail. The estimator still requires fitness above 0.3, at least 100 correspondences, rank at least three, and a finite transform. Rejected frames retain the last accepted reference and do not enter the map.

Registration metrics now include source/target point counts, correspondence count, selected voxel size, and a rejection reason. Episode provenance adds `registration_sampling_rule: bounded_voxel_refinement_v1`.

## Saved column approach

The same seed-101 cluttered-room robot-B camera replay previously rejected its first frame at 3.09 s, about 13.8 cm from the column face. With refinement, that frame has 352 surface matches at 1.5 cm resolution and is accepted. Its planar body-position error is about 0.45 mm.

Tracking remains accepted until 3.77 s, when the camera is about 1.4 cm from the face. That frame has 125 matches but only rank two, so it is correctly rejected by the unchanged rank requirement. The saved trajectory subsequently takes the camera through the column face. Extending successful tracking through that trajectory is not an appropriate clearance criterion.

Rejected frames fall from 84 to 57. This diagnoses and removes the earlier sampling failure; it does not solve collision avoidance or guarantee tracking arbitrarily close to a surface. Pose errors after a rejected frame describe a held estimate, not successful localization. Replay deliberately continues through failure; the live evaluator terminates on lost tracking.

The replay is saved at `outputs/exploration-planning/near-obstacle-validation/cluttered-room-b-replay.json`. Earlier results are retained under `body-origin-validation/replays/cluttered_room-b.json` in the same output tree.

## Fresh exploration checks

Both seed-101, two-robot runs reach the five-second horizon with no contacts, falls, recovery entries, or tracking failures. These run rendering, mapping, planning, locomotion, and the independent coverage collector together.

| Layout | Coverage | Normalized AUC | Body travel A / B |
| --- | --- | --- | --- |
| Branching corridor | 88.0% | 0.6915 | 1.12 / 1.13 m |
| Cluttered room | 69.9% | 0.5071 | 1.24 / 1.11 m |

| Layout / robot | Final planar error | Maximum planar error | Final orientation error |
| --- | --- | --- | --- |
| Corridor A | 3.58 cm | 3.65 cm | 0.25 degrees |
| Corridor B | 7.69 cm | 8.71 cm | 0.85 degrees |
| Cluttered room A | 2.02 cm | 5.17 cm | 1.82 degrees |
| Cluttered room B | 4.22 cm | 4.23 cm | 0.25 degrees |

Pose comparisons use input times through 4.99 s. Neither run reaches the configured 90% coverage threshold. These results combine the earlier navigation corrections with bounded refinement; they do not isolate its contribution to coverage. Runs were concurrent, so their wall times are not throughput benchmarks.

Episode histories and summaries are under `outputs/exploration-planning/near-obstacle-validation/<scenario>/`. The [preceding connected-room check](exploration-body-origin-validation.md) also reached five seconds without contacts or tracking failure, but predates this sampling change. Repeatability on a frozen revision, longer runs, additional seeds, and footprint-clearance checks remain before allocator comparisons.

## Regression coverage

Three analytical wall approaches start at 15, 8, and 4 cm and move 1 mm per frame. All three fail before the correction. With refinement they retain tracking, estimate translation within 1 mm, and keep the navigation cloud below 100 points while registration has at least 100 matches.

Two further cases verify that sparse pixels and line-shaped observations cannot manufacture support through refinement. Rejection leaves both the held pose and the accumulated map unchanged, even with deliberately incorrect live ground-truth inputs.

The shared SLAM, metrics, exploration, coordination, bridge, locomotion, and multi-robot integration suites pass 1,026 tests with 7 skips. The known Windows ZeroMQ IPC module is excluded.

## Reproduce

```powershell
$env:OMP_NUM_THREADS = '1'
uv run pytest tests/slam/test_icp_motion.py -k near_wall -q
uv run python scripts/diagnose_exploration_odometry.py --input outputs/exploration-planning/longer-validation/cluttered_room/diagnosis.json --robot robot_b --output outputs/exploration-planning/near-obstacle-validation/replay-rerun.json
uv run python scripts/diagnose_exploration_contacts.py --scenario cluttered_room --seed 101 --horizon 5 --output outputs/exploration-planning/near-obstacle-validation/cluttered-room-rerun
```

Generated artifacts are ignored by Git. This is development validation on a fixed seed, not a general tracking or clearance guarantee.
