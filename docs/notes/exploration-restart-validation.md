# Idle and restart correction

The calf-floor strike reproduced in the [five-second corridor check](exploration-longer-validation.md) is corrected for the recorded command sequence and reduced physics regressions. Localization drift and the separate column collision remain unresolved.

Correction revision: `c07892f`.

## Cause and change

Zero velocity previously stopped the gait clock but still calculated swing lift at the frozen phase. Two legs could remain tucked throughout an idle period. The standing-pose test only covered a fresh controller at phase zero, so it missed this state.

Commands inside the existing idle thresholds, at most 0.01 m/s translation and 0.01 rad/s yaw, now return the four-leg standing pose and reset the gait phase. Go2 `stand`, `stop`, and `recover` commands use the same path, preventing a later restart from resuming an old swing. Moving gait targets, speed limits, and clearance parameters are unchanged. Evaluation provenance adds `gait_idle_rule: standing_pose_phase_reset_v1`.

## Evidence

- Nine standing-pose regressions failed before the change: three stopping phases after straight, left-turning, and right-turning commands.
- A reduced sequence reproduces floor contact with the old controller at 0.31 s: walk at 0.4 m/s with 1 rad/s yaw for 0.10 s, idle for 0.18 s, then resume at 0.37 m/s with 1 rad/s yaw. The corrected controller has no non-foot floor contact in this case.
- Twelve physics cases cover three stopping phases, both turn directions, and zero-velocity versus explicit-stop commands. Every case keeps body height above 0.2 m, avoids non-foot floor contacts at the 100 Hz sampling cadence, and moves more than 0.03 m during the half-second restart phase.
- Replaying all 420 recorded corridor command frames removes the calf-floor strike at 4.10 s. The largest body-position difference from the old trace is 0.0305 m. This uses the original commands, not a new SLAM/planning run.
- All 269 locomotion and Go2 platform tests pass, including the unchanged forward-motion and constant-turn regressions. Mode tests also verify that standing, stopping, and recovery clear the suspended swing before resuming.
- The bridge, coordination, episode, and multi-robot integration check passes 234 tests with 7 skips. Real episode tests retain equal command and body traces with collectors enabled and disabled.

The local replay result is `outputs/exploration-planning/longer-validation/branching_corridor/physics-replay-idle-fix.json`; the original replay is retained separately. Reduced-sequence comparisons are in `outputs/exploration-planning/longer-validation/restart-probes.json`.

## Reproduce

```powershell
$env:OMP_NUM_THREADS = '1'
uv run pytest tests/locomotion tests/bridge/platforms/test_go2_platform.py -q
```

The physics tests run the actual Go2 bridge and controller without rendering or SLAM. They do not require saved output artifacts. This correction does not establish safety on uneven terrain, smooth every command transition, or validate a new five-second closed-loop trajectory. The next investigation is ICP drift, followed by obstacle clearance and another complete navigation validation.
