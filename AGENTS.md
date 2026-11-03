# Exploration validation

- Generate a top-view robot video with recorded coverage for every live exploration validation attempt, including early algorithm failures. This does not apply to unit-test invocations.
- Use `scripts/validate_exploration.py` for fresh live attempts. It saves diagnostics, then exports and verifies `top-view.mp4` before declaring the attempt complete.
- Keep each attempt in a new output directory. Preserve unsuccessful traces and videos. If simulation or video export fails, retain the artifacts and report the missing video explicitly.
- Commit changes in small, logical commits. Keep validation notes clear about actual end times, coverage, and remaining failures.
