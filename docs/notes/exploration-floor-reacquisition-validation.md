# Floor reacquisition validation

The [calibrated cluttered-room run](exploration-camera-calibration-validation.md) stopped at 6.66 s after its retained floor model lost newly observed floor points. The model could refine only already accepted points, so it could not recover when broad floor observations returned outside its band.

## Initial correction

Each frame tries the existing supported-plane detector. A fresh plane replaces history only when both imply camera-to-floor distances within 1.5 cm of one another at the current camera. The distance tolerance, bootstrap height band, support count, and extent requirements are unchanged. Comparing at the camera permits a small attitude correction even when distant floor residuals are larger.

Narrow views and camera-height dips fall back to the retained plane without refitting its truncated inliers. A competing raised plane beyond the local height tolerance cannot replace it. When a fresh plane recovers at least 40 points outside the historical band, matching raw obstacle observations are reclassified before voxelization. This removes stale floor evidence without deleting a whole voxel that may also contain a raised object.

The implementation uses estimated poses and observed points. Ground truth labels saved samples only after the run. The first correction records `floor_filter: supported_plane_reacquisition_v4`.

## Saved-frame checks

| Robot and saved time | Previously missed floor samples | Missed after reacquisition | Removed samples above 4 cm | Implied camera-height change |
| --- | --- | --- | --- | --- |
| A, 5.72 s | 331 | 0 | 0 | 1.19 cm |
| B, 6.33 s | 1,867 | 0 | 0 | 1.48 cm |

Results are saved in `outputs/exploration-planning/floor-history-validation/reacquisition-offline.json`. These are the recorded worst frames from `cluttered-room-02`, with each tracker initialized from its preceding recorded plane. They are not closed-loop results.

New regressions cover a two-degree attitude change, rejection of a 6 cm raised plane that would pass height calibration during a high stance, and removal of stale floor observations while preserving a low obstacle sharing a voxel. Existing tests retain sparse-view fallback and separate robot histories.

## Live attempts

Seed-101 attempts under `outputs/exploration-planning/floor-history-validation/` use runtime `3798649`. The related suites passed 510 tests with four skips.

| Attempt | Requested / actual duration | Termination | Coverage | Minimum camera clearance | Maximum planar pose error |
| --- | --- | --- | --- | --- | --- |
| `cluttered-room-03` | 10 / 7.71 s | all unreachable | 36.36% | 0.165 m | 0.067 m |
| `connected-rooms-03` | 5 / 5 s | horizon | 77.00% | 0.964 m | 0.003 m |
| `corridor-03` | 5 / 5 s | horizon | 68.64% | 0.235 m | 0.079 m |

Clutter and corridor recorded no unexpected contacts. Connected-room A again recorded a rear-right calf-floor contact at 3.30 s, with 0.82 mm penetration. No registration rejections occurred. Both clutter starts and corridor A finish without passable neighbors; connected-room robots and corridor B retain reachable frontiers.

All three videos decode successfully and match 772, 501, and 501 recorded body states respectively with zero replay position error. Runtime source hashes match the revision and remained unchanged during execution. Videos are `top-view.mp4` within each attempt directory, alongside previews and verification JSON.

## Rejecting weaker replacements

The first reacquisition attempt exposed a second failure. A camera dip can put the real floor just outside the bootstrap height band while allowing a tilted edge to pass. Height continuity alone then replaces a stronger historical plane with a weaker fresh proposal. At 0.66 s in connected rooms, historical residual-weighted support was 4,579 versus 3,280 for the replacement; the replacement missed 1,118 diagnostic floor samples and removed 116 samples above 4 cm.

The follow-up ranks both planes against the same finite observations using `sum(max(0, 1 - (distance / tolerance)^2))`. A replacement must improve this support as well as pass height continuity. Ties retain history. The distance tolerance remains 1.5 cm. Provenance becomes `floor_filter: ranked_plane_reacquisition_v5`.

The rule rejects three recorded bad replacements, reducing missed diagnostic floor samples from 1,118, 793, and 270 to zero, with no removed samples above 4 cm. It still reacquires the two earlier drift failures with 331 and 1,867 missed samples. Results are in `ranked-reacquisition-offline.json`. A synthetic floor and tilted raised surface regression reproduces the low-camera ambiguity, including an invalid sample.

The final support comparison is committed as `4b468f2`. Its related exploration, control, coordination, mapping, and selected integration suites passed 511 tests with four skips.

## Final live attempts

| Attempt | Requested / actual duration | Termination | Coverage | Minimum camera clearance | Maximum planar pose error |
| --- | --- | --- | --- | --- | --- |
| `cluttered-room-04` | 10 / 7.15 s | all unreachable | 37.91% | 0.129 m | 0.057 m |
| `connected-rooms-04` | 5 / 5 s | horizon | 67.69% | 0.699 m | 0.003 m |
| `corridor-04` | 5 / 5 s | horizon | 68.64% | 0.235 m | 0.079 m |

Each directory contains `top-view.mp4`, `top-view.png`, and `top-view.json`. All videos decode successfully. Replays match 716, 501, and 501 recorded body states respectively, with zero position error. Source hashes match runtime `4b468f2` and remained unchanged during execution. These are local ignored artifacts, not published downloads.

Clutter's maximum missed-floor counts fall from 3,411 to 197 for A and from 2,809 to 388 for B relative to `*-03`; final observations miss no diagnostic floor samples. Maximum removed samples above 4 cm fall from 156 to four for A and from 121 to one for B. Connected rooms records no missed floor or removed samples above 4 cm for either robot. Corridor A still has maxima of 32 missed samples and 18 removed samples above 4 cm; B has 227 missed and zero removed. All final observations have zero missed samples. This is an improvement in the measured classification failures, not proof of complete floor separation.

No registration rejections occur. Clutter and corridor record no unexpected contacts. The same connected-room A calf-floor contact remains at 3.30 s with 0.82 mm penetration. The changed routes do not establish a coverage improvement.

Both clutter starts still have no passable neighbors under planner inflation. Their nearest accumulated obstacle samples are at wall/column heights of 0.371 m and 0.201 m, rather than floor height. Corridor A also remains trapped; connected-room robots and corridor B retain reachable frontiers. Clutter B's camera reaches 12.9 cm clearance, below the configured 15 cm stand-off. Current-motion clearance and route departures are the next navigation correction; floor reacquisition alone does not enforce the planned envelope.

Run a new attempt with automatic video export:

```powershell
$env:OMP_NUM_THREADS = '1'
uv run --with imageio-ffmpeg python scripts/validate_exploration.py --scenario cluttered_room --seed 101 --horizon 10 --output outputs/exploration-planning/reacquisition-rerun/cluttered-room-01
```

This remains a flat-floor model. Large pose discontinuities can fail the continuity test; calibration ambiguity and accumulated map error remain limitations. Raw-point cleanup does not correct historical poses. Execution-time clearance and the recorded calf-floor contact are separate issues.
