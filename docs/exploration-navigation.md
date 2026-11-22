# Exploration navigation baseline

For the complete sensor-to-command pipeline, coordinate frames, map representations,
team information sharing, and the separate evaluation path, start with
[How data moves through the current exploration experiment](exploration-data-flow.md).

The shared navigation path now selects reachable frontier cells and separates floor observations before building the obstacle map. These corrections address the [first-scan failure](notes/exploration-first-scan-failure.md) and apply equally to interactive exploration and evaluation.

## Frontier targets

Cluster centroids remain useful for ranking regions. Navigation targets are actual free cells belonging to a cluster and reachable under the planner's existing inflation and eight-neighbor rules.

Clusters retain nearest, largest, or supplied bias scoring. Within a cluster, cells are ordered by distance from the current estimated position, then row and column. Other cells are tried before discarding a region. Occupied, inflated, and disconnected cells are excluded. Clearance caches are invalidated when grid contents, resolution, or the configured envelope change.

Candidates within the waypoint arrival radius are skipped, and smoothed paths retain the exact selected goal. This prevents repeatedly installing paths that the follower immediately considers complete. The [free-space correction](notes/exploration-free-space-correction.md) records the regression and live validation.

A scan clears the old route and goal before planning. A successful scan installs a new path and executes it on that frame, including the first scan at step 30. An unsuccessful scan leaves a persistent idle state, including frames without rescans. Initial forward movement is allowed only before the first scan; it cannot resume as a fallback after losing a route.

No frontiers, no feasible candidates, failed A* attempts, and scan exceptions all prevent stale-route execution. An idle robot keeps sensing and can resume after a successful rescan or an explicit waypoint command. Its teammate can continue exploring. Blocked planning and execution enter the bounded recovery policy described below; every recovery proposal still passes the execution guard. Episode provenance records `route_lifecycle: invalidate_on_rescan_v1`.

## Body and camera clearance

Exploration supplies a circular obstacle exclusion envelope that covers the configured footprint and the camera at every heading. Its radius is:

```text
max(footprint radius, camera mount offset norm + camera stand-off)
    + clearance margin + grid resolution / sqrt(2)
```

Defaults are a nominal 0.35 m Go2 footprint radius, 0.15 m camera stand-off, and 0.05 m planning margin. The mount comes from fixed calibration, not a simulator world pose. Its full 3D offset norm bounds horizontal camera reach during body tilt. The raster allowance encloses an occupied cell's half-diagonal. With the Go2 mount, the center-to-center exclusion is 0.638468 m at 0.05 m resolution and 0.673824 m at 0.10 m resolution. A missing mount retains the legacy coincident camera/body convention; it does not inherit the Go2 containment certificate below.

Goal filtering and A* share this envelope. Diagonal moves require both orthogonal neighbors to be passable. Smoothed paths retain both endpoints and reject touched raw occupied cells, including boundaries and corner contacts. Each continuous segment is checked against the exclusion disks around occupied-cell centers. Inflated cells are not treated as additional obstacles in that continuous check: doing so previously added a position-dependent raster allowance. Out-of-bounds points remain invalid. A failed check uses the unsmoothed A* route. The existing start-cell escape exception remains: an occupied or inflated start can step directly to a passable neighbor; it cannot make an inflated goal valid. Neither exception bypasses #4's execution guard. The bounded recovery policy handles rejection of that exception explicitly. Exploration disallows unknown center cells in route search and smoothing, matching the execution guard; the generic planner retains its optional unknown-space mode.

The [articulated geometry audit](notes/exploration-geometry-envelope-validation.md) verifies the existing camera-inclusive physical circle (0.553113 m) against a 0.549220 m continuous bound on all 23 collision primitives, including contact margins. It permits any body attitude and hip/thigh rotation, with calf joints in [-2.7227, -1.5] radians. Default gait targets and the sampled corrected replay lie within that knee interval. The nominal 0.35 m radius alone fails even for standing calf geometry; more extended knees can exceed the camera-inclusive circle too. The certificate is conditional and does not monitor joint states online. Changing geometry, mounting, stand-off, or gait range requires another audit.

This remains a conservative planning constraint on the observed map and can reject narrow passages. The margin is not a bound on localization error. The current execution guard stops on stale observations, checks projected motion, and replaces the conditional joint bound with the unrestricted sphere described below. Unknown obstacles and pose/map error remain limitations. Tracking acceptance thresholds and the coverage reference are unchanged. Episode provenance records `planning_clearance: body_camera_envelope_single_raster_v3`.

Exploration turns in place when heading error to the route exceeds `forward_heading_tolerance_rad`, default 0.25 radians. It resumes forward travel after alignment. This applies to both planned paths and explicit exploration waypoint targets. Small heading corrections retain simultaneous steering and forward motion. The [clearance validation](notes/exploration-camera-clearance-validation.md) records why clearance inflation alone was insufficient. Episode provenance records `path_following: align_heading_before_translation_v1`.

The Go2 gait limits changes in its active yaw command to 8 rad/s per second.
This bounds the abrupt hip-abduction and differential-stride changes during a
turn-to-walk transition that reproduced a rear-calf floor strike. It introduces
a short yaw response delay; translation commands and constant-command targets
retain their existing behavior. Explicit idle returns the standing pose and
clears both phase and yaw history immediately. After idle interrupts motion,
the gait waits for a total 80 ms standing-command interval before restarting.
The first moving gait target starts at its requested yaw. Crossing zero yaw during an active reversal keeps the
gait phase running. This is a development transition limit, not an attitude-aware
whole-leg clearance guarantee. Episode provenance records
`gait_transition_rule: bounded_active_yaw_slew_v1`. The
[calf-contact validation](notes/calf-contact-transition-validation.md) records
the replay, regression tests, live results, and remaining limitations.

## Camera and body frames

Navigation converts the SLAM camera estimate to a body estimate using fixed mounting calibration. Planning starts, waypoint steering, progress detection, free-space trajectories, and Voronoi allocation use that body estimate. Floor classification and obstacle insertion keep the camera origin. The [contact diagnosis](notes/exploration-contact-diagnosis.md) explains the former 90-degree steering mismatch, the gait-clearance correction, and remaining limits.

The ICP backend now uses [constrained surface odometry](notes/exploration-odometry-validation.md). It suppresses poorly observed motion directions and reports actual registration quality. Rejected observations hold the last accepted pose/reference and do not enter the map. The initial pose remains simulator-assisted; subsequent updates use depth only. Partially constrained updates can still accumulate position error, so acceptance is not a guarantee of accurate localization.

With mounting calibration, [odometry increments use the body origin](notes/exploration-body-origin-validation.md). This accounts for the camera's arc during turns instead of treating uncertain camera translation as zero. Calibration does not provide a live body pose or resolve all unobserved motion.

[Close-range registration](notes/exploration-near-obstacle-validation.md) can retain finer observed points when the normal map resolution removes too much support. Refinement is bounded and only affects registration. Map density and the overlap, correspondence, and rank requirements remain unchanged; diagnostics report the chosen resolution and reason for any rejection.

## Floor observations

[FloorTracker](../src/exploration/floor_filter.py) classifies each SLAM frame before its points enter the accumulated obstacle cloud. Each robot retains its own observed floor plane across frames. This avoids treating floor points spread across height bins by pose error and voxelization as obstacles.

The filter estimates local surface normals, considers approximately horizontal planes at the calibrated camera-to-floor distance, and requires at least 40 supporting points with extent in two directions. It ranks hypotheses by residual-weighted support, preferring lower planes on ties, before deduplication and refinement. This prevents a weak tilted wall/floor edge from displacing a strongly supported floor. Point ordering and candidate ordering are deterministic; it uses no global random state or reference geometry.

| Default | Value |
| --- | --- |
| Upright Go2 camera-to-floor distance | 0.32 m |
| Height tolerance | 0.04 m |
| Plane inlier distance | 0.015 m |
| Maximum tilt relative to estimated world up | 25 degrees |
| Minimum secondary-axis RMS spread | 0.08 m |

These requirements establish fresh planes. A robot retains its last plane for narrow views and camera-height changes during walking. A fresh supported plane can replace it only if their implied floor distances at the current camera differ by at most the existing 1.5 cm inlier tolerance and it has greater residual-weighted support across the current observations. Ties retain history. This permits correction of attitude drift whose error grows with viewing distance, while rejecting a competing raised plane with a larger local height difference or weaker support. History-only inliers do not refit the plane.

First acquisition removes matching raw observations already in the obstacle cloud. Reacquisition repeats that cleanup when a fresh plane recovers at least 40 points outside the old band. Filtering raw observations preserves raised points sharing a floor voxel. Episode provenance records `floor_filter: ranked_plane_reacquisition_v5`; floor diagnostics record each reacquisition. The [reacquisition validation](notes/exploration-floor-reacquisition-validation.md) records tests and live attempts.

Only plane inliers are removed. Before acquisition, unsupported points remain obstacle observations. `ExplorationConfig.ground_filter=False` bypasses separation. The camera-height calibration must be adapted for another platform or stance; this is a flat-floor Go2 baseline, not a general terrain classifier. Very shallow surfaces within the inlier tolerance are unresolved, and a broad raised surface within the calibration band can be ambiguous when the actual floor is hidden. Calibration and accumulated pose error can bias the tracked plane. The [floor-history validation](notes/exploration-floor-history-validation.md) records the results and remaining calibration issue.

Observed floor cells and the existing estimated-trajectory footprint supply free-space evidence to the planning grid. Unobserved neighbors remain unknown; proximity to a wall or floor sample cannot make them free. Occupied columns always take precedence, including low obstacles above observed floor. The grid uses one world-to-cell convention for insertion and querying. Coordination and navigation consume the same floor/obstacle projection. Trajectory stamping and partially observed maps retain their existing limitations.

Floor observations never define measured coverage. The independent depth-based collector and fixed reference area retain their existing definitions.

## Validation and remaining work

Tests cover occupied ring centroids, alternative cells within one cluster, inflated and disconnected targets, stable ordering, and retained replanned paths. Floor tests cover rigid pose shifts/tilts, wall-dominated scans, missing floor, raised surfaces, low obstacles, and a rendered 6 cm box.

The latest floor reacquisition correction passes 511 exploration, control, coordination, mapping, and selected integration tests with four skips. The preceding camera-calibration change passed 747 bridge, metrics, SLAM, and exploration tests with three skips; the subprocess SLAM module was excluded because this Windows ZeroMQ build does not support IPC. Real episode tests preserve command and body-trajectory equality with measurement collection enabled and disabled.

The [reacquisition validation](notes/exploration-floor-reacquisition-validation.md) reduced the measured floor-classification failures but did not pass the navigation gate. Clutter stopped at 7.15 s with 37.91% coverage and both starts blocked under inflation. Connected rooms and the corridor reached five seconds; corridor A remained trapped and connected-room A recorded a shallow calf-floor contact. No registration rejections occurred in those runs.

The subsequent [contact measurement validation](notes/contact-severity-validation.md) resolves the measurement scope of [Issue #1](https://github.com/ThePyProgrammer/argus/issues/1): physics-step identity, duration, force, impulse, and a versioned descriptive severity policy, with exact command and trajectory equality against the recorded baseline. The [gait transition correction](notes/calf-contact-transition-validation.md) resolves the reproduced calf strike in [Issue #2]. Its fresh connected-room seed-101 attempt reached the full **5.00 s** horizon with **74.909693% coverage**, zero non-foot contacts, zero falls, zero recovery entries, and zero failed planning attempts. The associated locomotion, control, episode, and video regression suites passed 361 tests. These results do not revalidate clutter, the corridor, other seeds, or longer horizons. Every fresh live validation exports a verified top-view video, including unsuccessful attempts.

The [Issue #3 geometry audit](notes/exploration-geometry-envelope-validation.md) establishes conditional articulated containment and tests corners, diagonals, narrow passages, and body/camera frame consistency at both 0.05 and 0.10 m resolution. The existing circle is retained, and continuous segment checks no longer add an extra traversed-cell allowance. Validation passed 537 distinct tests with four skips across the affected suite and one added fixture. A fresh connected-room seed-101 run reached 5.00 s with 74.909693% coverage and zero non-foot contacts, falls, recovery entries, or planning failures. All 500 commands and 501 trajectory samples exactly match the preceding gait-corrected run; this case shows preserved behavior, not a coverage gain.

The [development execution guard](notes/exploration-motion-clearance-validation.md)
now checks every exploration command against observed occupancy and a modeled
stopping tail. Planning and execution use an unrestricted all-joint collision
bound (0.658494 m before margin/raster allowance), avoiding an online assumption
about #3's knee interval. Missing calibration or stale state stops motion.
The affected suite passed 775 tests with seven skips. This implementation does
not establish arbitrary-drift safety, accurate maps, or successful recovery;
live validation and limitations are recorded in that note.

The initial guarded runs reached 10 s in clutter (36.7320% coverage) and 5 s in
connected rooms (76.5202%). Sampled camera stand-off remained above 0.15 m,
but each run recorded a rear-calf floor contact. Clutter stopped issuing motion
well before its horizon and repeatedly replanned nominally reachable routes.
These historical failures led to the restart/stopping correction below. The
validation note preserves both videos, exact contact severity, and offline
reproductions. Those initial attempts are not clean safety passes.

The [restart and stopping follow-up](notes/exploration-restart-settling-validation.md)
completes [#4's development execution-clearance scope](https://github.com/ThePyProgrammer/argus/issues/4).
An 80 ms standing interval removes the reproduced restart contacts. The shared
gait/guard command filter models that interval and active yaw slew. A one-second
posture-settling horizon with 0.20 m/s growing drift allowance covers 75 physical
stopping fixtures. Settled idle is recognized after one second of standing and
low estimated velocity; every new movement still reserves the full tail.
The affected suite passes **900 tests with seven skips**.

The baseline before bounded recovery reaches **5.00/5.00 s, 77.1523% coverage** in
connected rooms and **10.00/10.00 s, 31.2745% coverage** in clutter, both with zero
non-foot contacts or falls and verified videos. Minimum sampled static-obstacle
camera stand-off is 0.71833 m and 0.57511 m respectively. These sampled distances
are not continuous-time clearance certificates. Clutter A stops moving after
3.22 s, B never moves, and candidate selection repeats 1654 times despite zero
failed A* attempts. The larger stopping reserve improves the measured contact
outcome while reducing clutter coverage; sustained exploration is still unresolved.

The bounded policy and its evidence are recorded in
[Issue #5 validation](notes/exploration-bounded-recovery-validation.md).
The related scopes are tracked separately:

- [#5: blocked-start recovery](https://github.com/ThePyProgrammer/argus/issues/5): replan and recover without bypassing the execution clearance check or stopping a productive teammate.
- [#6: pose and map error](https://github.com/ThePyProgrammer/argus/issues/6): separate localization drift from floor/map errors and establish limits across development seeds and longer runs using the corrected gait.

The [pose/map validation](notes/exploration-pose-map-validation.md) records
controlled scan replay, separate pose and floor/map measurements, and a
three-layout, two-seed development matrix. It verifies that diagnostic recording
preserves commands over complete 8-second and 13.26-second episodes. Accepted
tracking can still produce observation-placement errors beyond the existing
50 mm planning-margin comparison. That comparison is not a certified uncertainty
allowance, and the observed navigation failures remain explicit.

The [executable-route follow-up](notes/exploration-executable-routes-validation.md)
adds bounded forward/backward route previews using the same execution guard
and shared gait command response. A geometric path alone no longer installs
a route: its nominal four-second forecast must include 0.15 m of accepted
translation. Selected frontier targets use an arrival tolerance of at most
one map cell, so nearby targets do not complete before meaningful travel.
Recovery prefers a predicted endpoint that enables navigation, within the
existing retry and time limits. A route replacement preserves uninterrupted
walking progress; turning, standing, and recovery motion cannot reset the
blockage budget. Every real command still passes the original clearance guard.

These forecasts rank local proposals on the current observed map; they do not
certify the whole route, physical motion response, or future sensing. The note
preserves the initial regressions, their corrections, and paired live evidence.
Pose/map uncertainty (#9), low-feature representation (#10), and the broader
sustained-exploration evaluation gate (#11) remain separate scopes.

Runtime uses #3's derivation extended to unrestricted knee rotation. Keep #4's
checks on every #5 recovery proposal and retain #6's measured limitations. The
severity thresholds remain development defaults; the contact fixes and geometry
certificate do not establish general collision safety or readiness for allocator
comparisons.

The original one-second checks resolved the first-scan failure but triggered recovery on every robot. The simulated-time correction below removes that false trigger. The [longer-run diagnostic](notes/exploration-recovery-validation.md) records subsequent contacts and the stale-path failure corrected above. Sustained exploration, controller safety, and long-horizon repeatability remain gates before the comparison campaign.

The earlier [five-second follow-up](notes/exploration-longer-validation.md) tested the camera/body and swing-lift corrections across all three layouts. Two runs stopped early; a calf-floor strike returned after restarting, and another robot hit a column. All layouts showed more than 0.5 m peak planar pose error for both robots at that revision. The subsequent [idle/restart correction](notes/exploration-restart-validation.md) removed that reproduced floor strike in physics replay: idle commands now return all legs to standing and reset the gait phase. These historical results precede the calibration, reacquisition, and active-yaw corrections described above.

Episode provenance records the exploration configuration and explicit versions for frontier targets, floor filtering, clearance, and route following. Selection timing includes reachable-cell filtering and candidate ranking, and excludes A* execution, mapping, and rendering.

## Mobility recovery

The former detector required 5 cm of movement on every frame. At the evaluation sensor rate of 100 Hz, that implies 5 m/s, far above the configured walking speed. It therefore triggered after 30 frames even while the robots were moving.

Recovery now requires two simulated seconds without 5 cm of net planar displacement while translation is commanded. Pure rotation commands instead require 0.1 radians of yaw progress. Idle commands reset the window. Vertical gait motion and small back-and-forth movement do not count as progress. Turning while walking still requires translation, so spinning against an obstacle cannot continually reset the timeout.

Both interactive exploration and evaluation use increasing sensor timestamps. A
planning failure with remaining frontiers, a blocked start, an execution
rejection, or commanded motion without progress enters `blocked`. The robot
stops, keeps sensing, and waits at least the configured settling interval before
`replanning`. Successful route installation enters `navigating`; it does not by
itself reset the failure budget.

Each blockage permits four replans and two recovery attempts, with at most 32
A* candidates per scan and a twelve-second deadline that includes all waiting,
planning, and recovery time. The policy reserves a route check after each
recovery within that same budget; it cannot spend the last replan before the
last recovery. It previews reverse at 0.60 m/s, turns at +/-0.50 rad/s, and
forward at 0.20 m/s using copies of the existing guard state. The second recovery prefers
a turn. A selected proposal is checked again by the actual guard on every
sensor frame; previews never consume pose, gait, or settling history.

Recovery ends after 0.10 m estimated translation in the commanded direction,
0.35 rad estimated rotation in the commanded direction,
or 1.5 seconds. An accepted command without observed motion reports
`no_progress`. A rejection stops and invalidates that recovery immediately.
After settling, another bounded replan can use newly observed free space.
Only 0.15 m of net displacement during accepted translation commands on an
installed navigation route resets the blockage budget. Turning and standing
reset the progress anchor, excluding their drift from subsequent walking.
Recovery motion and assigning a goal cannot reset the budget.

No safe candidate produces `failed: no_safe_recovery`, with each candidate's
guard reason retained. Retry exhaustion or the deadline also produce explicit
failures. Failed robots remain stopped and sensing until an explicit target
resets the policy. This describes infeasibility under the observed map, current
clearance model, and finite primitive set, not proof that no physical escape
exists. No obstacle removal, body-radius reduction, or clearance exception is
used. A productive teammate continues. If all active robots terminate and any
has failed navigation, evaluation ends with `navigation_failed`, preserving
actual time and measured coverage rather than reporting frontier exhaustion.

Configuration records all retry, duration, and progress thresholds. Episode
provenance identifies `bounded_commanded_replanning_v4`; command records and final
results include navigation states, reasons, retry counts, and recovery outcomes.
The legacy `StuckRecovery` helper remains for compatibility tests but is no
longer used by the live exploration loop.

These checks use estimated motion, not physical contact or goal progress. Pose drift can hide a blockage; movement without useful exploration can satisfy the mobility threshold. The two-second window is a development default, not a tuned safety guarantee.
