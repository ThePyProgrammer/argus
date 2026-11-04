# Camera calibration validation

Follow-up: [ranked floor reacquisition](exploration-floor-reacquisition-validation.md) addresses the retained-plane failures below and records fresh videos. Motion clearance remains an open navigation gate.

SLAM used integer pixel coordinates with a principal point defined for half-integer coordinates. The resulting half-pixel bias tilted reconstructed floors. A tracked floor plane could then classify distant wall-base points as floor.

## Correction

`CameraIntrinsics.from_fov` now places the principal point at `((width - 1) / 2, (height - 1) / 2)`, matching Open3D's integer depth-sample coordinates. Focal length is unchanged. The coverage collector also uses integer pixel centers, preserving its physical rays and four-pixel support rule. The contract is versioned as `floor-depth-support-v2`; episode provenance records `camera_calibration: integer_pixel_centers_v2`.

This is shared calibration, not a relaxed floor tolerance or registration threshold. See the [measurement contract](../exploration-measurements.md) for conversion of old calibration values.

## Geometry and regression checks

An oblique MuJoCo floor is reconstructed through the actual depth-to-cloud path and checked against its authored height, without fitting a plane. Resolutions are 64 x 48, 65 x 49, and 320 x 240. The old calibration missed the plane by up to roughly 6 cm at low resolution and 1.3 cm at 320 x 240. The corrected reconstruction stays within 0.2 mm, including raster/depth precision error.

A rendered connected-room initial observation now supports both distant floor classification and preservation of 5 cm raised points. This catches the extrapolation error that simple frontal-camera tests missed.

The bridge, metrics, SLAM, and exploration suites passed 747 tests with three skips. The Windows-incompatible ZeroMQ IPC subprocess module was excluded. A subsequent focused floor-tracker run passed seven tests, including the new distant-obstacle regression.

Old and new coverage implementations produced identical masks for all six saved initial camera views after converting the principal points. The comparison is saved in `outputs/exploration-planning/floor-history-validation/coverage-calibration-parity.json`. It checks measurement consistency on those frames; new navigation traces can still change coverage.

## Live validation

The fresh `*-02` attempts under `outputs/exploration-planning/floor-history-validation/` use runtime revision `e775776`. Seed 101, two Go2 robots, `OMP_NUM_THREADS=1`. Each attempt runs through `scripts/validate_exploration.py`, which exports and verifies its video before reporting completion.

| Attempt | Requested / actual duration | Termination | Coverage | Minimum camera clearance | Maximum planar pose error |
| --- | --- | --- | --- | --- | --- |
| `cluttered-room-02` | 10 / 6.66 s | all unreachable | 37.48% | 0.150 m | 0.045 m |
| `connected-rooms-02` | 5 / 5 s | horizon | 67.69% | 0.699 m | 0.003 m |
| `corridor-02` | 5 / 5 s | horizon | 68.64% | 0.235 m | 0.079 m |

No registration rejections occurred. Connected-room robot A recorded a rear-right calf-floor contact at 3.30 s, with 0.82 mm penetration. Clutter and corridor recorded no unexpected contacts. Camera clearance is a post-run geometry diagnostic, not a controller input or a collision guarantee.

Both cluttered-room starts finish without passable neighbors. Corridor robot A has the same condition; robot B retains reachable frontiers. Both connected-room robots retain reachable frontiers.

All runtime source hashes match the recorded revision, allowing for Git line-ending conversion, and remain unchanged during execution. Videos verify 667, 501, and 501 body states respectively, with zero replay position error. All three MP4s decode successfully. Each attempt retains diagnostics, a final preview, and `top-view.json` verification metadata. Outputs are local ignored artifacts; the documentation and reproduction command are committed.

## Remaining floor failure

The geometry correction is verified, but the cluttered-room trace regresses from the floor-history-only attempt's 10 s and 74.12% coverage. This is not a navigation improvement or a passed evaluation gate.

The retained plane can lose the floor when SLAM drift moves new floor observations outside its 1.5 cm band. Refining only already accepted points then cannot recover it. At 6.33 s, robot B's 1,867 diagnostic floor samples lie between -7.45 and -2.26 cm in estimated map height; the stored plane remains near zero. Every sample is rejected. Some wall-base points instead match the stale plane. Robot A also loses 331 floor samples at 5.72 s.

Applying the stateless detector to those two saved worst frames recognizes every diagnostic floor sample and removes no samples labelled above 4 cm. It still cannot classify the earlier sparse views. Results are saved as `cluttered-room-02/floor-reacquisition-diagnosis.json`. This supports adding controlled reacquisition when broad floor evidence returns, while retaining history for narrow views. It does not justify widening the distance band, which could erase low obstacles.

The next correction should test reacquisition under pose drift, rejection of competing raised planes, and reclassification of stale floor points already stored as obstacles. It also needs a motion-clearance check against current observations before a robot becomes trapped inside inflation. Corridor A's nearest final mapped obstacle is 0.513 m from its estimated body position, inside the roughly 0.674 m planning exclusion. The calf-floor contact requires a separate gait-transition check. Longer runs, repeated seeds, and allocation comparisons remain gated on these failures.

Reproduce in a new directory; preserve every attempt and its video:

```powershell
$env:OMP_NUM_THREADS = '1'
uv run --with imageio-ffmpeg python scripts/validate_exploration.py --scenario cluttered_room --seed 101 --horizon 10 --output outputs/exploration-planning/calibration-rerun/cluttered-room-01
```
