# Articulated planning envelope validation (Issue #3)

## Result and declared pose range

The existing Go2 camera-inclusive circle contains all **23 collision primitives**
within the declared knee range. Its physical radius is **0.553112887 m** before
adding planning or raster margins. A conservative continuous bound on the whole
robot is **0.549219779 m**, including each primitive's configured contact margin.
The bound leaves **3.893 mm** inside the physical envelope. The separate 0.05 m
planning margin is not needed to obtain this containment result.

The certificate permits every heading, roll, pitch, hip angle, and thigh angle.
Each calf joint must lie in **[-2.7227, -1.5] radians**. These are geometric
conditions, not a claim that every such configuration is stable or reachable.
Current default gait calf targets lie in [-2.1, -1.8] radians. Recorded frame
samples from the corrected Issue #2 replay span **[-2.050742, -1.841152] radians**;
this comparison does not inspect every physics step or establish future tracking
error bounds. There is no online enforcement of the certified range yet.

The nominal **0.35 m** platform radius alone is insufficient: a regression fixture
places an actual point on a rear-calf cylinder outside it even in standing pose.
The larger camera-plus-stand-off circle provides containment for the current
default under the certificate's assumptions. Do not remove or reduce the camera term,
change the model, or change the gait range without auditing the resulting envelope.
The audit fails closed if its supported joint hierarchy, hinge axes, or collision
primitive types change.

The full model joint range is **not** certified. A front leg at hip 0, thigh -1.2,
and calf -0.83776 radians has a foot reaching beyond 0.6 m horizontally while the
body is upright. That is an actual geometric counterexample, not just a loose
upper bound. Handling joint states outside the declared range belongs in
[#4's execution clearance checks](https://github.com/ThePyProgrammer/argus/issues/4).

## Why this covers continuous motion in the declared range

`src/exploration/evaluation/geometry_audit.py` derives its dimensions from the
compiled benchmark model. It includes boxes, cylinders, spheres, and capsules,
and excludes noncolliding visual meshes. It bounds complete primitives, not
only link origins or foot centers.

For each leg, triangle inequality adds root-to-hip distance to a sphere centered
on the hip. Hip rotation cannot enlarge this sphere. The thigh origin lies on
its hinge axis, so thigh rotation cannot change distance from the hip. For calf
geometry, the audit maximizes

```text
norm(thigh_offset + calf_offset + Ry(calf_angle) * geom_center)
```

over the entire closed calf interval, using endpoints and any internal sinusoid
maximum. It then adds a containing sphere for the primitive and its contact
margin. The joint layout checks are necessary parts of this proof. A sphere
around the body origin bounds its horizontal projection under any body attitude.
The full 3D camera offset norm plus stand-off similarly bounds the camera.

Independent MuJoCo forward-kinematic tests exercise standing, straight walking,
left/right turns, reverse, recovery-rate turns, gait phases, body tilt, and joint
interval endpoints. A dense independent rotation test checks the analytic extrema.
These samples check the implementation; the continuous claim comes from the bound.

## Grid clearance and frame consistency

The configured radii remain unchanged:

| Grid resolution | Body/camera radius | Planning margin | Occupied-cell half diagonal | Exclusion radius |
| --- | --- | --- | --- | --- |
| 0.05 m | 0.553112887 m | 0.05 m | 0.035355339 m | 0.638468226 m |
| 0.10 m | 0.553112887 m | 0.05 m | 0.070710678 m | 0.673823566 m |

The audit found an extra source of conservatism in `path_is_clear`: it rejected
every touched inflated cell even when the exact segment stayed outside all
exclusion disks. This reserved extra space depending on where the segment lay
inside a grid cell. The corrected check rejects raw occupied-cell touches and
out-of-bounds points, then uses continuous distance to the occupied-cell centers
for the already-inflated radius. It no longer treats an entire inflated cell as
an additional obstacle. Corner and diagonal fixtures still reject unsafe cuts.

At both resolutions, narrow-corridor tests check reachability, A*, and segment
clearance immediately above and below the usable grid-center gap. The passing
gaps would fail if a second half-diagonal were added. A* still uses discrete cell
centers and its existing conservative diagonal-neighbor rule; this is not an
optimal oriented-footprint planner. Inflation caching now also includes grid
resolution, so reusing a cell array at a different scale cannot reuse stale costs.

Fixed mounting calibration converts the estimated camera pose to the body origin
used by the geometry audit, planning, and waypoint steering. Tests cover both
resolutions, headings, and roll/pitch with deliberately unrelated ground-truth
camera poses in the frame. Mapping retains the camera origin. No simulator body
pose or geometry result is supplied to the live navigator by this audit.

The existing blocked-start escape exception and unsmoothed-route fallback are
unchanged; they are not a certificate of safe recovery or physical execution.
Those limitations remain in #4 and #5. Episode provenance now records
`planning_clearance: body_camera_envelope_single_raster_v3`.

## Reproduction and checks

```powershell
$env:OMP_NUM_THREADS = '1'
.venv/Scripts/python.exe scripts/audit_planning_envelope.py --output outputs/exploration-planning/geometry-envelope/audit-01 --replay outputs/exploration-planning/calf-contact/replay-final-after/replay.json
```

Use a new output directory. This is an offline kinematic audit: it does not step
physics, run exploration, or claim new coverage. The
[audit JSON](../../outputs/exploration-planning/geometry-envelope/audit-01/audit.json)
contains per-geometry bounds, parameters, source hashes, and replay comparison.
The [top-view overlay](../../outputs/exploration-planning/geometry-envelope/audit-01/envelope.svg)
shows sampled collision silhouettes against the nominal, physical, and planning
circles. Illustration sampling is separate from the continuous certificate.

```powershell
$env:OMP_NUM_THREADS = '1'
.venv/Scripts/python.exe -m pytest tests/exploration tests/control tests/coordination tests/bridge/platforms/test_go2_platform.py -q -p no:cacheprovider --basetemp outputs/exploration-planning/geometry-envelope/test-tmp-01
```

The affected suite passed **536 tests with four skips**. A subsequently added
standing-pose counterexample test passed separately, for **537 distinct passing
tests**. The new geometry/grid/frame subset had already passed 91 tests before
that final fixture was added. The affected suite ran outside the Windows sandbox's
known pytest temporary-directory restriction.

## Fresh live validation

The segment-check correction can change runtime path acceptance. A fresh
connected-room seed-101 attempt used runtime **`e6173bc`**, one OpenMP thread,
and a five-second requested horizon:

```powershell
$env:OMP_NUM_THREADS = '1'
.venv/Scripts/python.exe -u scripts/validate_exploration.py --scenario connected_rooms --seed 101 --horizon 5 --output outputs/exploration-planning/geometry-envelope/connected-rooms-01
```

The attempt reached **5.00/5.00 s**, terminating at the horizon with
**74.909693% coverage**, **zero non-foot contacts**, **zero falls**, **zero
recovery entries**, and **zero failed planning attempts**. Team body XY travel
was **1.546105 m**. All nine detailed contact episodes were expected foot support.
All source hashes remained unchanged. The 413.58 s wall duration includes
diagnostic measurement work and is not an isolated performance benchmark.

The [verified top-view video](../../outputs/exploration-planning/geometry-envelope/connected-rooms-01/top-view.mp4)
includes recorded coverage. Its
[verification report](../../outputs/exploration-planning/geometry-envelope/connected-rooms-01/top-view.json)
checks all **501 body-position samples with zero error**. There are 351 video
frames lasting 14.04 s, including half-speed playback and hold frames; the actual
simulation duration is five seconds. The
[complete diagnostics](../../outputs/exploration-planning/geometry-envelope/connected-rooms-01/diagnosis.json)
and all generated artifacts remain local in the ignored output directory.

The [baseline comparison](../../outputs/exploration-planning/geometry-envelope/connected-rooms-01/baseline-comparison.json)
finds exact equality with the corrected Issue #2 run for **all 500 commands,
501 trajectory samples, coverage measurements, and detailed contact summaries**.
This seeded case therefore retains its previous behavior. The grid fixtures
demonstrate the corrected acceptance of clear segments; this live run does not
demonstrate a coverage gain or increased passage availability.

Clutter, the corridor, other seeds, and longer horizons have not been revalidated
for this revision. Execution clearance, conditional-range enforcement, safe
blocked-start recovery, and pose/map uncertainty remain in #4-#6. Completing this
geometry audit does not establish those behaviors or general collision safety.
