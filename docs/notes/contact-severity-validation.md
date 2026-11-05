# Contact identity and severity measurement (Issue #1)

The original connected-room seed-101 trace reported a rear-right calf-floor
contact at 3.30 s as `robot_obstacle`. Its 0.82 mm penetration alone did not
establish duration or impact severity. This change measures those quantities;
it does not change the gait or attempt to prevent the contact (Issue #2).

## Implementation and contract

- `f009822` adds raw contact records, per-geometry events, and the descriptive
  `go2-descriptive-contact-v1` policy.
- `13932d7` captures every physics step before the frame-end forward pass,
  attaches/detaches the observer with the episode, exports the geometry catalog
  and raw history, and documents timing and interpretation.
- `b3b8b0f` preserves partial diagnostic records on infrastructure exceptions.

The [measurement contract](../exploration-measurements.md#physics-step-contacts)
defines support, leg-floor, body-floor, robot-obstacle, robot-robot, and self
contact; normal-force sums, impulse, touching duration, and clearance debounce;
and censoring at the start/end of measurement. Raw samples include positive
distance margins and all robot-involving manifold points. Fall transitions
remain separate sensor-cadence observations from the existing platform state.
Severity labels are report-only and cannot terminate an episode. Thresholds
are development reporting conventions, not calibrated damage/safety limits.

## Automated validation

The metrics, exploration, control, and multi-robot bridge regression command
passed **605 tests**. A subsequent targeted command passed **7 tests**, including
two newly added cases for actual Go2 part ownership and failure-path raw export
(the other five repeat the existing validation workflow checks).

```powershell
$env:OMP_NUM_THREADS = '1'
.venv/Scripts/python.exe -m pytest tests/metrics tests/exploration tests/bridge/test_multi_bridge.py tests/control -q -p no:cacheprovider --basetemp outputs/test-tmp/contact-metrics-02
.venv/Scripts/python.exe -m pytest tests/exploration/test_evaluation_episode.py::test_go2_catalog_distinguishes_feet_calf_and_base_collision_shapes tests/exploration/test_validation_video_workflow.py -q -p no:cacheprovider --basetemp outputs/exploration-planning/contact-test-tmp-01
```

Earlier sandbox invocations hit Windows access errors in pytest's temporary
directories, including a workspace-local directory. The successful commands
ran outside that restriction; those setup errors were not assertion failures.
The task's disposable `outputs/test-tmp/contact-metrics-*` directories were
removed after testing. Live attempts and their artifacts are retained.

Tests cover expected foot support, calf brushes, sustained contact, forceful
wall contact, separate fall transitions, inclusive threshold boundaries,
multiple manifold points, contact-order reversal, clearance gaps, censoring,
invalid inputs, and raw-buffer ownership. Real MuJoCo tests verify solver-force
capture for Euler/implicit/implicitfast and a wall impact. RK4 is explicitly
rejected. Bridge tests verify capture before frame refresh, including contact
that disappears before the sensor frame. Real episode tests preserve exact
commands and body trajectories with collection enabled/disabled, including the
first frontier scan, and check observer cleanup and retained partial samples.

## Live validation

The connected-room attempt uses runtime `b3b8b0f`, seed 101, a requested 5 s
horizon, and one OpenMP thread. The existing local comment edit in
`exploration_metrics.py` is preserved; per-file hashes in `run.json` identify
the exact tested source. The severity policy was documented before the run.

```powershell
$env:OMP_NUM_THREADS = '1'
.venv/Scripts/python.exe -u scripts/validate_exploration.py --scenario connected_rooms --seed 101 --horizon 5 --output outputs/exploration-planning/contact-severity-validation/connected-rooms-01
```

The attempt completed at **5.00 simulated seconds**, reaching the requested
horizon with **67.68512944% coverage** and no falls. The measured episode wall
time was 813.34 s; this is not an isolated instrumentation-overhead benchmark.
All recorded source hashes remained unchanged during the attempt.

| Measurement | Result |
| --- | --- |
| Physics intervals retained | 2,500, each 0.002 s |
| Raw robot-involving manifold point samples | 14,287 |
| Per-geometry support episodes | 8 (the four feet on each robot) |
| Leg-floor episodes | 1, robot A rear-right calf, geometry IDs 0 and 63 |
| Body-floor / obstacle / robot-robot / self episodes | 0 / 0 / 0 / 0 |
| Legacy broad robot-obstacle counter | 1, unchanged |
| Falls | 0 for both robots |

The calf-floor event spans **3.294–3.314 s**, with **0.020 s** touching duration,
**39.9585 N** peak normal force, **0.317094 N s** normal impulse, and **0.82121 mm**
maximum penetration. Ten physics-step point samples contribute to the event.
Both censoring flags are false: its onset and sufficient subsequent absence
were observed. The prior sensor-frame diagnostic only identified the touch at
3.30 s and could not establish these quantities.

Under the policy frozen before this run, the event is **`unclassified_contact`**:
its peak exceeds the 20 N incidental-contact limit, while duration, peak, and
impulse remain below the sustained/forceful thresholds. We do **not** relabel it
as harmless or change the thresholds to fit this result. Its `leg_floor` kind
and measured quantities distinguish it from wall impacts and falls even when
the severity policy leaves that intermediate case unclassified.

The [baseline comparison](../../outputs/exploration-planning/contact-severity-validation/connected-rooms-01/baseline-comparison.json)
against `floor-history-validation/connected-rooms-04/diagnosis.json` shows exact
numeric equality of all **500 commands and 501 body-position samples**, as well
as outcome, elapsed time, episode events, and navigation provenance. Both runs
reach five seconds with identical coverage. This establishes measurement
neutrality for this recorded case, not general long-horizon repeatability.

The [verified top-view video](../../outputs/exploration-planning/contact-severity-validation/connected-rooms-01/top-view.mp4)
contains the recorded coverage. Its [verification report](../../outputs/exploration-planning/contact-severity-validation/connected-rooms-01/top-view.json)
checks all 501 replayed body samples with **zero position error**; the video has
351 frames and a 14.04 s duration including half-speed playback and hold frames.
The [complete diagnostic JSON](../../outputs/exploration-planning/contact-severity-validation/connected-rooms-01/diagnosis.json)
retains the geometry catalog, severity configuration, per-event measurements,
raw contact history, body traces, commands, and coverage. These generated files
remain local under the ignored output directory.

## Remaining limitations

The leg still touches the floor; gait correction is separate work. The reporting
thresholds require calibration before making physical safety claims. Falls
retain the existing sensor-cadence height classifier, and sub-physics-step
contacts remain unresolved. Raw histories are retained in memory until export,
so storage and memory grow with run duration. This one live case and the unit
fixtures validate the measurement path; they do not close the navigation gate
or establish success on other seeds and longer horizons.
