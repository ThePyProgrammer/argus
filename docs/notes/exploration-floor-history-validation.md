# Floor history validation

The floor-history correction removes the early stops observed in the preceding [clearance validation](exploration-camera-clearance-validation.md) on the same development seed and short horizons. This is a navigation smoke result, not an allocation benchmark.

## Cause and correction

Walking lowered the camera to 0.277 to 0.279 m, just outside the stateless floor detector's 0.28 m lower bound. Other frames contained narrow floor strips that could not independently establish a plane. Rejected floor points accumulated as obstacles and eventually surrounded the robots' planning starts.

Each robot now retains a supported floor plane in its estimated map frame. It reuses that plane through camera bobbing and narrow views, and refines it from broad matching observations. Bootstrap requirements and the 1.5 cm distance tolerance are unchanged. First acquisition reclassifies old raw points before voxelization, so a raised obstacle sharing a floor voxel survives.

## Live attempts

Seed 101, two Go2 robots, `OMP_NUM_THREADS=1`. Artifacts are under `outputs/exploration-planning/floor-history-validation/`. All three attempts have `validation.json`, diagnostics, coverage, and a verified `top-view.mp4`.

| Attempt | Requested / actual duration | Termination | Coverage | Minimum camera clearance | Maximum planar pose error |
| --- | --- | --- | --- | --- | --- |
| `cluttered-room-01` | 10 / 10 s | horizon | 74.12% | 0.191 m | 0.022 m |
| `connected-rooms-01` | 5 / 5 s | horizon | 73.39% | 0.798 m | 0.015 m |
| `corridor-01` | 5 / 5 s | horizon | 73.21% | 0.235 m | 0.071 m |

No unexpected contacts, falls, recoveries, or registration rejections were recorded. The cluttered-room video verifies all 1,001 recorded body states with zero replay error; each other video verifies 501. All three videos decode successfully, and all source manifests report unchanged runtime files during execution.

The terminal maps retain reachable frontiers for both cluttered-room and connected-room robots. Corridor robot A still has no passable neighbors under inflation; robot B retains reachable frontiers. Reaching the horizon does not establish that every robot can keep moving. These endpoints do not establish long-horizon safety or repeatability.

The targeted suites passed 506 tests with four skips across exploration, control, coordination, mapping, and selected integration tests. Six added regressions cover floor history, independent robot state, raised surfaces, and removal before voxelization.

## Remaining calibration issue

Reclassifying six saved failure frames using an initial observed plane removed all previously missed diagnostic floor samples. One connected-room sample also removed eight wall-base points labelled above 4 cm. The learned plane was slightly tilted, so its height grew with distance. Those diagnostic height labels undo pose error but still depend on correct depth unprojection.

The live `*-01` diagnostics also label some removed wall-base samples above 4 cm, with per-frame maxima of 31 in clutter, 60 in connected rooms, and 18 in the corridor. Successful navigation does not establish correct floor separation.

An initial experiment shifting the principal point by half a pixel greatly reduced the tilt. The subsequent [calibration correction](exploration-camera-calibration-validation.md) checks this against independently rendered geometry. These attempts and videos remain evidence of the floor-history change alone. Execution departures from planned routes and long-horizon drift remain separate limitations.
