# Deferred Items

- Shared quick gate `uv run --project /home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-a886e2eb5f61fe7c2 python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py tests/locomotion/test_locomotion_evaluation_exports.py tests/locomotion/test_locomotion_baseline_regression.py -q` failed in `test_analytical_trot_flat_ground_fixed_seed_regression` because `distance_xy_m` remains `0.0` in episode rows while commanded velocity is nonzero. This is the Phase 06 Plan 02 distance export gap, not part of Plan 06-01's active-command files.
