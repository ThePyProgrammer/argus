# First-contact diagnosis

Development fixture: `branching_corridor`, seed 101, two Go2 robots, 100 Hz sensor/control updates. These checks explain the early contacts; they are not an allocator comparison or a general collision-free navigation result.

## What touched what

Before the corrections, the first recorded contacts were the left rear calf against the floor: robot B at 0.32 seconds and robot A at 0.33 seconds. These were real non-foot contacts, not expected foot support mislabeled as collisions. The first planned route centerlines stayed roughly 0.69 m and 1.05 m from fixture walls/boxes respectively. Wall inflation does not explain these first floor contacts.

Physics-only isolation reproduced calf-floor contact without SLAM or planning: straight commands of 0.4 and 0.8 m/s first contacted at 0.48 and 0.32 seconds. The analytical gait's extra thigh reduction during foot lift could lower the knee/calf too far.

## Corrections

**Navigation frame.** The camera is mounted 0.4 m ahead of the body and 0.05 m above it. Its X axis points sideways. Navigation previously treated that camera position and axis as the body origin and forward direction, introducing a quarter-turn heading error and a displaced planning start.

Both bridges now attach fixed camera-mount calibration to each frame. Exploration and Voronoi allocation convert the SLAM camera estimate into an estimated body pose. Mapping, floor filtering, perception, and measured coverage retain camera poses. No live simulator body pose or reference geometry enters navigation. Calibration currently requires a fixed camera attached directly to the robot root; legacy producers without calibration retain their coincident-frame convention.

**Swing clearance.** `GaitParams.swing_thigh_min=0.60` limits the extra thigh reduction used for lift. A turn allowance increases that limit by up to 0.05 radians at 1 rad/s of yaw, accounting for reduced clearance during body roll. If the stride already requests a lower angle, no extra reduction is added. Stride endpoints remain unchanged, avoiding new jumps between swing and stance. This is a level-floor Go2 development calibration, not a terrain-independent clearance guarantee.

Eleven two-second physics cases cover forward speeds 0.24, 0.4, and 0.8 m/s and left/right turns at 0.4 and 0.8 m/s with yaw commands of 0.5 and 1 rad/s. They have no non-foot floor contacts, maintain body height above 0.2 m, and move more than 0.2 m. Straight travel changes from 0.347 to 0.333 m at a 0.4 m/s command and from 0.592 to 0.573 m at 0.8 m/s. The contact reduction therefore has a modest locomotion cost. The existing forward-motion regression remains unchanged and passes: the robot travels 0.528 m against its 0.5 m requirement.

Development attempts are retained under `outputs/exploration-planning/contact-diagnosis/`: reversing the lift sign removed contacts but severely impaired movement and was rejected; bounds of 0.45 and 0.55 radians retained contacts. A fixed 0.65-radian bound removed contacts but failed the existing forward-distance requirement. Fixed bounds of 0.60 and 0.625 passed that movement check but retained turn contacts. The selected turn-dependent limit preserves phase-boundary targets and passes both checks without weakening their assertions. These are tuning runs, not independent final-study samples.

## Why robot A initially observes zero floor coverage

An independent MuJoCo ray check finds 403 reference floor-cell centers inside A's initial camera frustum. Every ray hits `obstacle_southeast` first. B has 1,284 visible reference centers, all hit the floor, and the depth-based collector agrees.

The initial zero is therefore correct occlusion, not missing depth or a pose-estimator error in the collector. Moving alone does not guarantee a view of eligible floor. This proves the initial condition; it does not establish visibility for every frame of the historical five-second run.

## Validation

The relevant runtime, measurement, and locomotion suites pass 975 tests with 7 skips. The known Windows ZeroMQ IPC test module is excluded. Tests verify camera/body transforms under rotated poses, preservation of estimated pose error rather than substitution of ground truth, phase-boundary continuity, contact clearance, forward progress, and the independent occlusion explanation. The existing collector-on/off command and body-trajectory checks still pass.

With both corrections, the seed-101 corridor reaches a one-second horizon with zero non-foot contacts, falls, or recovery entries. Both robots receive goals and move. Measured coverage is 53.4%; A observes one eligible cell and B observes 1,434. The saved diagnostic is `outputs/exploration-planning/contact-diagnosis/final-corrected/diagnosis.json`. A preceding run with only the body-frame correction recorded two floor-contact episodes over the same horizon. This short check validates the reproduced failure, not long-run navigation reliability.

## Remaining limits

The [five-second follow-up](exploration-longer-validation.md) finds a later calf-floor strike after restarting, a column collision in another layout, and substantial localization drift. Two layouts terminate early. The one-second result above establishes only the short reproduction; sustained navigation remains unresolved.

ICP camera-position errors at the first planning frame are about 0.112 m for A and 0.156 m for B. Fixed mount calibration removes the frame mismatch, not localization drift. The planner's 0.15 m hard inflation also warrants review against the platform's 0.35 m footprint radius before claiming obstacle clearance. Longer trajectories, recovery, other speeds, and uneven terrain remain unvalidated by these short contact checks.

Episode provenance records `estimated_body_from_camera_mount_v1`, `bounded_swing_thigh_lift_v1`, and the gait parameters. Earlier navigation traces and coverage results must not be treated as results for this revised baseline.

## Reproduce

```powershell
$env:OMP_NUM_THREADS = '1'
uv run python scripts/diagnose_exploration_contacts.py --scenario branching_corridor --seed 101 --horizon 1 --output outputs/exploration-planning/contact-diagnosis/current
uv run pytest tests/locomotion/test_gait_clearance.py tests/bridge/test_camera_mount.py -q
```

The diagnostic saves raw contact geometry, input-time-aligned pose errors, first planning grids/routes, initial RGB/depth, independent visibility rays, and episode histories. It is an observer; these geometry and truth checks never feed back into control.
