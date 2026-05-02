# Locomotion Benchmark Harness

Argus locomotion is benchmark-first. The v4.0 harness wraps the current Go2 MuJoCo locomotion path in a Gymnasium-style `ArgusGo2Env` boundary, runs named controller × scenario × seed matrices, and writes machine-readable artifacts for comparison. It is the place to measure controller changes before claiming improvement.

Current Argus locomotion is analytical trot plus MuJoCo position actuators.

For the architectural rationale, see `docs/adr/0018-use-reproducible-gymnasium-style-locomotion-benchmark-harness.md`. For the controller-family scope boundary, see `outputs/locomotion-rd-systems.md` and `docs/adr/0019-benchmark-locomotion-before-adding-new-controller-families.md`.

## First smoke benchmark

Run the flat-ground analytical baseline with explicit controller, scenario, and seed flags:

```bash
uv run argus eval-locomotion --controller analytical_trot --scenario flat_ground --seed 101 --seed 202
```

The command evaluates the supported `analytical_trot` controller in the `flat_ground` scenario for seeds `101` and `202`, then writes a timestamped run directory under `outputs/locomotion-evals/<timestamp>/`.

## Environment surface

`ArgusGo2Env` follows the Gymnasium reset/step shape used by evaluation, regression tests, and future controller adapters:

- `ArgusGo2Env.reset(seed=...)` returns `(observation, info)`. The seed controls the scenario sample, including spawn pose, terrain parameters, command schedule, and disturbances where applicable.
- `ArgusGo2Env.step(action)` returns `(observation, reward, terminated, truncated, info)`.
- `terminated` means the metrics collector detected a locomotion failure. `truncated` means the episode reached `max_episode_steps`.
- `info["locomotion_metrics"]` carries per-step metric payloads. Terminal steps also include `info["locomotion_metrics_summary"]`.

The observation dictionary contains these keys:

| Key | Meaning |
|-----|---------|
| `qpos` | MuJoCo generalized position snapshot, padded to the harness shape. |
| `qvel` | MuJoCo generalized velocity snapshot, padded to the harness shape. |
| `command` | Current desired planar velocity command: vx, vy, omega. |
| `previous_action` | Last 12 joint-position targets sent through the locomotion path. |

The environment-supported action modes are listed below. argus eval-locomotion currently runs `velocity_command`; `joint_position` and `residual_baseline` are env-supported seams that fail fast in evaluation until explicit action sources exist.

| Action mode | Use |
|-------------|-----|
| `velocity_command` | Three-value planar velocity command routed through the selected controller. This is the default benchmark/evaluator mode for `analytical_trot`. |
| `joint_position` | 12-value direct joint-position env seam for controller families that own joint target generation; not currently evaluator-runnable without an explicit action source. |
| `residual_baseline` | 12-value residual-over-baseline env seam for future residual-policy work; not currently evaluator-runnable without a trained residual policy/action source. |

## Reward and metrics

The environment currently returns reward `0.0`. Locomotion quality is inspected through metrics, not reward shaping. That is deliberate: v4.0 benchmarks the existing baseline and export surfaces before pretending there is a training reward worth optimizing.

Metric families in the artifacts and `info` payloads are:

- **Command tracking** — measured velocity error, tracking RMSE, and distance traveled against the command schedule.
- **Stability** — base height, roll, pitch, success, and failure reason summaries.
- **Action quality** — smoothness, joint-limit violations, and position-servo effort/saturation proxies. These are position-servo proxy metrics, not torque or energy measurements.
- **Contact/terrain proxies** — foot slip, foot clearance, duty factor, and terrain/contact summaries where the MuJoCo contact data supports them.

## Scenario catalog

Use scenario ids exactly as shown below. CLI flags and matrix config files use these ids, not display names.

| Scenario id | Purpose |
|-------------|---------|
| `flat_ground` | Deterministic baseline terrain for smoke tests and regression comparisons. |
| `low_friction` | Plane terrain with reduced friction to stress tracking and slip metrics. |
| `slope` | Sloped terrain with sampled parameters. |
| `rough_heightfield` | Randomized heightfield terrain for rough-ground response. |
| `push_disturbance` | Flat terrain with scheduled external push disturbance. |

## Matrix config workflow

For larger comparisons, put the matrix in JSON and pass it to the same CLI:

```json
{
  "controllers": ["analytical_trot"],
  "scenarios": ["flat_ground"],
  "seeds": [101, 202],
  "action_mode": "velocity_command",
  "max_episode_steps": 500,
  "sim_steps_per_frame": 10,
  "heightfield_size": 16
}
```

```bash
uv run argus eval-locomotion --matrix-config path/to/matrix.json
```

Repeated CLI flags can still be used for quick runs; use JSON when the matrix needs to be saved, reviewed, or regenerated.

## Saved-run regeneration

Regenerate summary and comparison artifacts from an existing run directory without rerunning MuJoCo:

```bash
uv run argus eval-locomotion --from-run-dir outputs/locomotion-evals/<timestamp>/
```

This reads the saved artifacts and rewrites `summary.json` and `comparison.md` for the run.

## Artifact glossary

Each evaluation writes a timestamped directory under `outputs/locomotion-evals/<timestamp>/`.

| Artifact | Purpose |
|----------|---------|
| `manifest.json` | Reproducibility metadata: invocation, matrix, environment config, git commit, files, and run list. |
| `steps.jsonl` | Per-step metric rows for detailed offline inspection. |
| `episodes.csv` | One row per controller/scenario/seed episode with aggregate metrics. |
| `summary.json` | Machine-readable aggregate summary and metric directions. |
| `comparison.md` | Human-readable Markdown comparison tables. |

## Controller-family boundary matrix

The matrix is intentionally hard-edged. If a family is unavailable or deferred, do not describe it as supported just because there is a seam. v4.0 does not ship trained RL policies, MPC, WBC, ROS/hardware behavior, torque-control locomotion, or perception-conditioned locomotion.

| Controller family | Status now | Argus hook/seam | Why supported/deferred | Prerequisite to unlock | R&D rationale link |
|-------------------|------------|-----------------|------------------------|------------------------|--------------------|
| analytical gait | supported now | Controller id `analytical_trot`; `argus eval-locomotion`; default `velocity_command` action mode | Existing deterministic Raibert-style analytical trot produces Go2 joint-position targets through MuJoCo position actuators. | Keep regression and metrics gates green before changing baseline behavior. | `outputs/locomotion-rd-systems.md`; `docs/adr/0019-benchmark-locomotion-before-adding-new-controller-families.md` |
| residual RL | registered placeholder unavailable | Controller id `residual_policy`; residual-over-baseline seam via `residual_baseline` action mode | Placeholder exists so the benchmark boundary is stable, but no trained residual policy artifact ships in v4.0. | Train/evaluate residual policy artifacts and define promotion criteria against the analytical baseline. | `outputs/locomotion-rd-systems.md`; `docs/adr/0019-benchmark-locomotion-before-adding-new-controller-families.md` |
| direct RL | registered placeholder unavailable | Controller id `direct_policy`; joint-position action seam | Placeholder exists, but v4.0 has no trained direct policy and no training pipeline in scope. | Add training/evaluation infrastructure, policy artifacts, and reproducibility gates. | `outputs/locomotion-rd-systems.md`; `docs/adr/0019-benchmark-locomotion-before-adding-new-controller-families.md` |
| MPC | registered placeholder unavailable | Controller id `mpc`; model-based controller seam | Requires dynamics/contact solver infrastructure not implemented in v4.0. | Add model-based-control infrastructure, contact assumptions, and benchmark evidence. | `outputs/locomotion-rd-systems.md`; `docs/adr/0019-benchmark-locomotion-before-adding-new-controller-families.md` |
| WBC | registered placeholder unavailable | Controller id `wbc`; whole-body-control seam | Requires torque/whole-body-control infrastructure not implemented in v4.0. | Add torque/control allocation assumptions, state/contact estimation, and benchmark evidence. | `outputs/locomotion-rd-systems.md`; `docs/adr/0019-benchmark-locomotion-before-adding-new-controller-families.md` |
| ROS/hardware | deferred/no runnable v4.0 implementation | Future adapter boundary only; no runnable controller id | v4.0 is simulation-only and CPU-first; ROS 2 and hardware deployment are out of scope. | Define hardware/ROS architecture, timing, state estimation, safety, and deployment gates. | `outputs/locomotion-rd-systems.md`; `docs/adr/0019-benchmark-locomotion-before-adding-new-controller-families.md` |
| perception-conditioned locomotion | deferred/no runnable v4.0 implementation | Future perception-to-control integration seam only; no runnable controller id | Current benchmark isolates locomotion control from perception-conditioned policy behavior. | Define perception-conditioned observations, latency handling, safety behavior, and benchmark scenarios. | `outputs/locomotion-rd-systems.md`; `docs/adr/0019-benchmark-locomotion-before-adding-new-controller-families.md` |
