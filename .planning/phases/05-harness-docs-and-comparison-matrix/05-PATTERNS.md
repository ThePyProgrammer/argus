# Phase 05: harness-docs-and-comparison-matrix - Pattern Map

**Mapped:** 2026-05-01
**Files analyzed:** 3 new/modified files
**Analogs found:** 3 / 3

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `docs/locomotion-benchmark.md` | documentation | request-response / file-I/O | `README.md` + `docs/adr/0018-use-reproducible-gymnasium-style-locomotion-benchmark-harness.md` | role-match |
| `README.md` | documentation | request-response | `README.md` existing Locomotion System section | exact |
| `tests/test_locomotion_benchmark_docs.py` | test | file-I/O | `tests/locomotion/test_locomotion_evaluation_exports.py` + `tests/test_main_args.py` | role-match |

## Pattern Assignments

### `docs/locomotion-benchmark.md` (documentation, request-response / file-I/O)

**Analog:** `README.md` and `docs/adr/0018-use-reproducible-gymnasium-style-locomotion-benchmark-harness.md`

**Markdown onboarding pattern** (`README.md` lines 305-320):
```markdown
## The Locomotion System

### Benchmark Before Bragging

Argus locomotion is deliberately benchmark-first. `ArgusGo2Env` wraps the Go2 MuJoCo path in a Gymnasium-style `reset(seed=...)` / `step(action)` contract with named scenarios, deterministic resets, action modes, controller metadata, and per-step/per-episode metrics.

The default controller is still the analytical trot, but it now sits behind the same registry seam as future residual-policy, direct-policy, MPC, and WBC families. Unsupported families are explicit placeholders until the control infrastructure and evidence exist. No vibes-based robot-dog claims.

Run the smoke benchmark:

```bash
uv run argus eval-locomotion --controller analytical_trot --scenario flat_ground --seed 101 --seed 202
```

Evaluation artifacts are written under `outputs/locomotion-evals/` as JSONL steps, CSV episodes, a machine-readable summary, a manifest with reproducibility metadata, and a Markdown comparison table.
```

**Architecture/rationale prose pattern** (`docs/adr/0018-use-reproducible-gymnasium-style-locomotion-benchmark-harness.md` lines 17-29):
```markdown
Argus already has a working Go2 locomotion path: high-level velocity commands feed an analytical Raibert-style trot controller, which outputs 12 Unitree Go2 joint-position targets tracked by MuJoCo position actuators. That is useful. It is not yet a benchmark.

The v4.0 planning work makes locomotion comparison a first-class goal. Future controller families — residual policies, direct policies, MPC, WBC, and hardware-oriented adapters — need a shared boundary for reset, step, action shape, observation, metrics, and reproducibility. Without that boundary, every controller comparison becomes a bespoke script with just enough differences to make the numbers untrustworthy. That is how benchmarks rot.

The approved v4.0 roadmap requires:

- a Gymnasium-style `ArgusGo2Env` with `reset(seed=...)` and `step(action)` semantics;
- named scenarios including `flat_ground`, `low_friction`, `slope`, `rough_heightfield`, and `push_disturbance`;
- deterministic seeded resets for spawn pose, terrain parameters, command schedule, and disturbances;
- action modes for velocity command, joint-position target, and residual-over-baseline control;
- a locomotion controller protocol/registry with analytical trot as the default baseline;
- machine-readable JSONL/CSV/summary exports and reproducibility metadata;
- a baseline regression test for the analytical trot.
```

**CLI facts to document** (`src/main.py` lines 93-148):
```python
eval_parser = subparsers.add_parser(
    "eval-locomotion",
    help="Run offline locomotion controller/scenario/seed evaluations",
)
eval_parser.add_argument(
    "--controller",
    action="append",
    default=None,
    help="Controller id to evaluate; repeat for a matrix (default: analytical_trot)",
)
eval_parser.add_argument(
    "--scenario",
    action="append",
    default=None,
    help="Scenario id to evaluate; repeat for a matrix (default: flat_ground)",
)
eval_parser.add_argument(
    "--seed",
    action="append",
    type=int,
    default=None,
    help="Seed to evaluate; repeat for a matrix (default: 101, 202)",
)
eval_parser.add_argument(
    "--matrix-config",
    default=None,
    metavar="PATH",
    help="Optional JSON matrix config; repeated CLI flags override matrix dimensions",
)
eval_parser.add_argument(
    "--from-run-dir",
    default=None,
    metavar="PATH",
    help="Regenerate summary.json and comparison.md from a saved run directory",
)
eval_parser.add_argument(
    "--output-root",
    default="outputs/locomotion-evals",
    metavar="PATH",
    help="Directory for timestamped evaluation artifacts (default: outputs/locomotion-evals)",
)
eval_parser.add_argument("--max-episode-steps", type=int, default=500)
eval_parser.add_argument("--sim-steps-per-frame", type=int, default=10)
eval_parser.add_argument("--heightfield-size", type=int, default=16)
eval_parser.add_argument("--action-mode", default="velocity_command")
eval_parser.add_argument("--max-matrix-runs", type=int, default=1000)
eval_parser.add_argument(
    "--allow-locomotion-failures",
    action="store_true",
    help="Write artifacts but exit zero when evaluated locomotion failures occur",
)
eval_parser.add_argument(
    "--verbose",
    action="store_true",
    help="Print per-run progress and metric snippets",
)
```

**Saved-run regeneration pattern** (`src/main.py` lines 280-285):
```python
if getattr(args, "from_run_dir", None):
    run_dir = Path(args.from_run_dir)
    regenerate_comparison(run_dir)
    print(f"summary: {run_dir / 'summary.json'}")
    print(f"comparison: {run_dir / 'comparison.md'}")
    return 0
```

**Artifact contract to document** (`src/locomotion/evaluation.py` lines 30-55):
```python
_ARTIFACT_FILES = ("manifest.json", "steps.jsonl", "episodes.csv", "summary.json", "comparison.md")
_EPISODE_CSV_FIELDS = (
    "run_id",
    "controller_id",
    "scenario_id",
    "seed",
    "action_mode",
    "commanded_velocity",
    "command_source",
    "success",
    "failure_reason",
    "step_count",
    "tracking_rmse",
    "distance_xy_m",
    "base_height_min_m",
    "base_height_max_deviation_m",
    "roll_abs_max_rad",
    "pitch_abs_max_rad",
    "action_smoothness_mean",
    "position_servo_effort_mean",
    "joint_limit_violation_count",
    "actuator_saturation_count",
    "foot_slip_mean",
    "foot_clearance_mean",
    "duty_factor_mean",
)
```

**Environment reset/step surface to document** (`src/locomotion/env.py` lines 76-183):
```python
def reset(
    self,
    *,
    seed: int | None = None,
    options: dict[str, Any] | None = None,
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    """Reset the episode and return an observation plus reproducibility info."""
    ...
    observation = extract_observation(self._data, self._command, self._previous_action)
    return observation, self._info()

def step(
    self,
    action: np.ndarray,
) -> tuple[dict[str, np.ndarray], float, bool, bool, dict[str, Any]]:
    """Apply a mode-specific action and return the Gymnasium five-tuple."""
    ...
    reward = 0.0
    terminated = metrics_step.failure_reason is not None
    truncated = self._step_count >= self.config.max_episode_steps
    info = self._info()
    info["locomotion_metrics"] = self._metrics.latest_info_payload()
    if terminated or truncated:
        summary = self._locomotion_summary_payload()
        self._last_locomotion_metrics_summary = copy.deepcopy(summary)
        info["locomotion_metrics_summary"] = summary
    return observation, reward, terminated, truncated, info
```

**Observation surface to document** (`src/locomotion/observations.py` lines 14-43):
```python
def build_observation_space() -> spaces.Dict:
    """Build the state-only Phase 1 observation space."""
    return spaces.Dict(
        {
            "qpos": spaces.Box(
                low=-np.inf,
                high=np.inf,
                shape=_QPOS_SHAPE,
                dtype=np.float32,
            ),
            "qvel": spaces.Box(
                low=-np.inf,
                high=np.inf,
                shape=_QVEL_SHAPE,
                dtype=np.float32,
            ),
            "command": spaces.Box(
                low=-np.inf,
                high=np.inf,
                shape=_COMMAND_SHAPE,
                dtype=np.float32,
            ),
            "previous_action": spaces.Box(
                low=-np.inf,
                high=np.inf,
                shape=_PREVIOUS_ACTION_SHAPE,
                dtype=np.float32,
            ),
        }
    )
```

**Action modes to document** (`src/locomotion/actions.py` lines 12-15 and 61-87):
```python
ACTION_MODE_VELOCITY = "velocity_command"
ACTION_MODE_JOINT_POSITION = "joint_position"
ACTION_MODE_RESIDUAL_BASELINE = "residual_baseline"
...
def available_action_modes() -> list[str]:
    """Return sorted action mode names supported by the benchmark wrapper."""
    return sorted(_ACTION_MODES)
...
def build_action_space(mode: str) -> spaces.Box:
    """Build the Gymnasium action space for an action mode.

    Args:
        mode: One of ``velocity_command``, ``joint_position``, or
            ``residual_baseline``.

    Raises:
        ValueError: If *mode* is not registered.
    """
```

**Scenario catalog to document** (`src/locomotion/scenarios.py` lines 30-59):
```python
SCENARIOS: dict[str, ScenarioSpec] = {
    "flat_ground": ScenarioSpec(
        scenario_id="flat_ground",
        display_name="Flat Ground",
        terrain_kind="plane",
    ),
    "low_friction": ScenarioSpec(
        scenario_id="low_friction",
        display_name="Low Friction",
        terrain_kind="plane",
    ),
    "slope": ScenarioSpec(
        scenario_id="slope",
        display_name="Slope",
        terrain_kind="slope",
        randomizes_terrain=True,
    ),
    "rough_heightfield": ScenarioSpec(
        scenario_id="rough_heightfield",
        display_name="Rough Heightfield",
        terrain_kind="heightfield",
        randomizes_terrain=True,
    ),
    "push_disturbance": ScenarioSpec(
        scenario_id="push_disturbance",
        display_name="Push Disturbance",
        terrain_kind="plane",
        has_disturbance=True,
    ),
}
```

**Controller-family matrix facts** (`src/locomotion/controllers.py` lines 54-69 and 467-488):
```python
RESIDUAL_POLICY_UNAVAILABLE_REASON = (
    "Residual policy controllers require trained policy artifacts and are deferred "
    "until a future RL milestone."
)
DIRECT_POLICY_UNAVAILABLE_REASON = (
    "Direct policy controllers require trained policy artifacts and are deferred "
    "until a future RL milestone."
)
MPC_UNAVAILABLE_REASON = (
    "MPC controllers require dynamics/contact solver infrastructure and are deferred "
    "until a future model-based-control milestone."
)
WBC_UNAVAILABLE_REASON = (
    "WBC controllers require torque/whole-body-control infrastructure and are deferred "
    "until a future model-based-control milestone."
)
...
@locomotion_controller(name="residual_policy", display="Residual Policy")
class ResidualPolicyController(_UnavailableControllerBase):
    CAPABILITIES = _placeholder_capabilities("residual_policy", "residual_joint_position")
    UNAVAILABLE_REASON = RESIDUAL_POLICY_UNAVAILABLE_REASON

@locomotion_controller(name="direct_policy", display="Direct Policy")
class DirectPolicyController(_UnavailableControllerBase):
    CAPABILITIES = _placeholder_capabilities("direct_policy", "joint_position")
    UNAVAILABLE_REASON = DIRECT_POLICY_UNAVAILABLE_REASON

@locomotion_controller(name="mpc", display="Model Predictive Control")
class MPCController(_UnavailableControllerBase):
    CAPABILITIES = _placeholder_capabilities("mpc", "joint_position")
    UNAVAILABLE_REASON = MPC_UNAVAILABLE_REASON

@locomotion_controller(name="wbc", display="Whole-Body Control")
class WBCController(_UnavailableControllerBase):
    CAPABILITIES = _placeholder_capabilities("wbc", "torque_or_joint_position")
    UNAVAILABLE_REASON = WBC_UNAVAILABLE_REASON
```

**Validation/error handling pattern for factual docs**: keep guide content grounded in the source excerpts above. Do not invent command flags, scenario ids, artifact names, or controller statuses.

---

### `README.md` (documentation, request-response)

**Analog:** `README.md` existing Four Commands + Locomotion System sections

**Compact command-card pattern** (`README.md` lines 13-24):
```markdown
## Four Commands

The core workflows fit on one screen.

```
uv run argus --scene office           Start the simulation + dashboard
uv run argus --scene office --static  Watch without moving
uv run argus --control explore        Single-robot autonomous exploration
uv run argus eval-locomotion          Run the locomotion smoke benchmark
```

Open the browser. Watch robots explore an office. See their point clouds merge in real time. Click the ground to command them. Choose SLAM and perception backends, inspect metrics, toggle between cloud/voxel/mesh views, or run the same locomotion baseline through seeded benchmark scenarios. Everything streams over a single WebSocket or exports as machine-readable evaluation artifacts.
```

**README link/style pattern** (`README.md` lines 26-49):
```markdown
## Table of Contents

- [When Robots Are Cheap, Coordination Is Everything](#when-robots-are-cheap-coordination-is-everything)
- [The Perception Problem](#the-perception-problem)
- [Philosophical Foundations](#philosophical-foundations)
- [How Argus Works](#how-argus-works)
- [The SLAM Pipeline](#the-slam-pipeline)
- [The Exploration System](#the-exploration-system)
- [The Coordination Layer](#the-coordination-layer)
- [The Bridge Layer](#the-bridge-layer)
- [The Platform Layer](#the-platform-layer)
- [The Locomotion System](#the-locomotion-system)
- [The Research Harness Pattern](#the-research-harness-pattern)
```

**Existing locomotion copy to update, not duplicate** (`README.md` lines 313-320):
```markdown
Run the smoke benchmark:

```bash
uv run argus eval-locomotion --controller analytical_trot --scenario flat_ground --seed 101 --seed 202
```

Evaluation artifacts are written under `outputs/locomotion-evals/` as JSONL steps, CSV episodes, a machine-readable summary, a manifest with reproducibility metadata, and a Markdown comparison table.
```

**Planner guidance:** Add a short card/link to `docs/locomotion-benchmark.md`, keep README terse, and avoid copying the full controller-family matrix into README.

---

### `tests/test_locomotion_benchmark_docs.py` (test, file-I/O)

**Analog:** `tests/locomotion/test_locomotion_evaluation_exports.py` and `tests/test_main_args.py`

**Imports/pathlib file-read pattern** (`tests/locomotion/test_locomotion_evaluation_exports.py` lines 7-11):
```python
from __future__ import annotations

import csv
import json
from pathlib import Path
```

For the new doc-content test, copy the `Path` import pattern and use repository-root constants:
```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
GUIDE = ROOT / "docs" / "locomotion-benchmark.md"
```

**Fast plain-assert test style** (`tests/test_main_args.py` lines 206-233):
```python
def test_eval_locomotion_parser_accepts_repeatable_matrix_flags(monkeypatch):
    """LOC-EVAL-01 D-01 D-02: eval-locomotion is a dedicated CLI subcommand."""
    import src.main as main_module

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "argus",
            "eval-locomotion",
            "--controller",
            "analytical_trot",
            "--scenario",
            "flat_ground",
            "--seed",
            "101",
            "--seed",
            "202",
        ],
    )

    args = main_module.parse_args()

    assert args.command == "eval-locomotion"
    assert args.controller == ["analytical_trot"]
    assert args.scenario == ["flat_ground"]
    assert args.seed == [101, 202]
```

**Artifact-name assertion pattern** (`tests/locomotion/test_locomotion_evaluation_exports.py` lines 21-22 and 125-142):
```python
_ARTIFACT_NAMES = {"manifest.json", "steps.jsonl", "episodes.csv", "summary.json", "comparison.md"}
...
assert {path.name for path in result.run_dir.iterdir()} == _ARTIFACT_NAMES  # D-05 / T-04-02.

manifest = _read_json(result.run_dir / "manifest.json")
# LOC-EVAL-03 / D-08 / T-04-03: reproducibility metadata is top-level manifest data.
assert set(manifest) >= {
    "git_commit",
    "invocation_args",
    "matrix",
    "environment_config",
    "action_mode",
    "created_at",
    "files",
    "runs",
}
assert set(manifest["files"]) == _ARTIFACT_NAMES
```

**Required-content assertion pattern to adapt** (`tests/locomotion/test_locomotion_evaluation_exports.py` lines 204-209):
```python
markdown = (result.run_dir / "comparison.md").read_text(encoding="utf-8")
assert "# Locomotion Evaluation Comparison" in markdown
assert "## Overall by Controller" in markdown
assert "## By Controller and Scenario" in markdown
assert "tracking_rmse ↓" in markdown
assert "success_rate ↑" in markdown
```

**Recommended new test skeleton:**
```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
GUIDE = ROOT / "docs" / "locomotion-benchmark.md"
SMOKE_COMMAND = (
    "uv run argus eval-locomotion --controller analytical_trot "
    "--scenario flat_ground --seed 101 --seed 202"
)
ARTIFACTS = ("manifest.json", "steps.jsonl", "episodes.csv", "summary.json", "comparison.md")
FAMILIES = (
    "analytical",
    "residual RL",
    "direct RL",
    "MPC",
    "WBC",
    "ROS/hardware",
    "perception-conditioned locomotion",
)


def test_readme_links_locomotion_benchmark_guide():
    readme = README.read_text(encoding="utf-8")
    assert "docs/locomotion-benchmark.md" in readme
    assert SMOKE_COMMAND in readme


def test_locomotion_benchmark_guide_required_content():
    guide = GUIDE.read_text(encoding="utf-8")
    assert SMOKE_COMMAND in guide
    assert "--matrix-config" in guide
    assert "--from-run-dir" in guide
    for artifact in ARTIFACTS:
        assert artifact in guide


def test_controller_family_matrix_required_content():
    guide = GUIDE.read_text(encoding="utf-8")
    for family in FAMILIES:
        assert family in guide
    assert "outputs/locomotion-rd-systems.md" in guide
    assert "analytical_trot" in guide
```

**Anti-pattern:** Do not use `subprocess.run`, `uv run`, or environment construction in these tests. Phase 5 tests are content guards only.

## Shared Patterns

### Documentation truth source hierarchy
**Source:** `05-CONTEXT.md` lines 63-72 and implementation files listed below  
**Apply to:** `docs/locomotion-benchmark.md`, README command card, documentation tests

Use these files as canonical sources before authoring prose:
- CLI command/flags: `src/main.py` lines 93-148 and 269-325.
- Artifact names and summary/comparison generation: `src/locomotion/evaluation.py` lines 30-73, 294-345, 623-642, 693-739.
- Gymnasium reset/step behavior: `src/locomotion/env.py` lines 76-183.
- Observation keys/shapes: `src/locomotion/observations.py` lines 14-43.
- Action modes: `src/locomotion/actions.py` lines 12-15 and 61-87.
- Scenario catalog: `src/locomotion/scenarios.py` lines 30-64.
- Metric families and proxy labels: `src/locomotion/metrics.py` lines 57-58, 237-269, 393-432, and `src/locomotion/evaluation.py` lines 56-73.
- Controller availability/deferred boundary: `src/locomotion/controllers.py` lines 54-69, 397-443, and 467-488.

### Hard support/deferred controller boundary
**Source:** `src/locomotion/controllers.py` lines 397-443 and 446-488  
**Apply to:** controller-family matrix in `docs/locomotion-benchmark.md`
```python
@locomotion_controller(name="analytical_trot", display="Analytical Trot")
class AnalyticalTrotController:
    """Adapter that delegates exactly to the existing analytical trot gait."""

    CAPABILITIES = _analytical_capabilities()
    ...

    @classmethod
    def available(cls) -> tuple[bool, str | None]:
        return True, None
...
class _UnavailableControllerBase:
    ...
    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        raise UnavailableControllerError(self.UNAVAILABLE_REASON)

    @classmethod
    def available(cls) -> tuple[bool, str | None]:
        return False, cls.UNAVAILABLE_REASON
```

### Artifact generation and saved-run comparison
**Source:** `src/locomotion/evaluation.py` lines 623-638 and 339-345  
**Apply to:** guide artifact glossary, saved-run regeneration section, tests checking artifact names
```python
def regenerate_comparison(run_dir: Path) -> dict[str, Any]:
    """Regenerate summary and Markdown comparison from saved artifacts only."""

    run_path = Path(run_dir)
    manifest = json.loads((run_path / "manifest.json").read_text(encoding="utf-8"))
    rows = _read_episode_csv(run_path / "episodes.csv")
    return write_comparison_artifacts(run_path, rows, manifest)
...
def _write_artifacts(
    run_dir: Path,
    step_rows: list[dict[str, Any]],
    episode_rows: list[dict[str, Any]],
    manifest: dict[str, Any],
) -> None:
    _write_json(run_dir / "manifest.json", manifest)
    with (run_dir / "steps.jsonl").open("w", encoding="utf-8") as fp:
        for row in step_rows:
            fp.write(json.dumps(_jsonable(row), separators=(",", ":"), sort_keys=True) + "\n")
    with (run_dir / "episodes.csv").open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(_EPISODE_CSV_FIELDS), extrasaction="ignore")
        writer.writeheader()
        for row in episode_rows:
            writer.writerow({field: _csv_safe(row.get(field, "")) for field in _EPISODE_CSV_FIELDS})
    write_comparison_artifacts(run_dir, episode_rows, manifest)
```

### Content tests stay cheap
**Source:** `05-CONTEXT.md` lines 31-34 and `tests/locomotion/test_locomotion_evaluation_exports.py` lines 204-209  
**Apply to:** `tests/test_locomotion_benchmark_docs.py`
```python
markdown = (result.run_dir / "comparison.md").read_text(encoding="utf-8")
assert "# Locomotion Evaluation Comparison" in markdown
assert "## Overall by Controller" in markdown
assert "## By Controller and Scenario" in markdown
assert "tracking_rmse ↓" in markdown
assert "success_rate ↑" in markdown
```
Adapt to `README.read_text()` and `GUIDE.read_text()`. Do not execute MuJoCo, the smoke command, or `argus eval-locomotion`.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| None | n/a | n/a | All Phase 5 files have direct or role-match analogs in docs/tests. |

## Metadata

**Analog search scope:** `/home/prannayag/pragnition/robotics/argus/docs`, `/home/prannayag/pragnition/robotics/argus/README.md`, `/home/prannayag/pragnition/robotics/argus/tests`, `/home/prannayag/pragnition/robotics/argus/src/locomotion`, `/home/prannayag/pragnition/robotics/argus/src/main.py`  
**Files scanned:** 18 listed/read surfaces plus phase context/research files  
**Project skills checked:** `.claude/skills/desloppify/SKILL.md` read; not applicable to docs/content-test mapping  
**Pattern extraction date:** 2026-05-01
