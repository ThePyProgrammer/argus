"""Markdown content guards for the locomotion benchmark guide."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
GUIDE = ROOT / "docs" / "locomotion-benchmark.md"
SMOKE_COMMAND = "uv run argus eval-locomotion --controller analytical_trot --scenario flat_ground --seed 101 --seed 202"
ARTIFACTS = ("manifest.json", "steps.jsonl", "episodes.csv", "summary.json", "comparison.md")
FAMILIES = (
    "analytical gait",
    "residual RL",
    "direct RL",
    "MPC",
    "WBC",
    "ROS/hardware",
    "perception-conditioned locomotion",
)


def test_readme_links_locomotion_benchmark_guide_and_artifacts():
    readme = README.read_text(encoding="utf-8")

    assert "docs/locomotion-benchmark.md" in readme
    assert SMOKE_COMMAND in readme
    for artifact in ARTIFACTS:
        assert artifact in readme


def test_locomotion_benchmark_guide_required_content():
    guide = GUIDE.read_text(encoding="utf-8")
    guide_lower = guide.lower()

    assert SMOKE_COMMAND in guide
    assert "--matrix-config" in guide
    assert "--from-run-dir" in guide
    for token in ("qpos", "qvel", "command", "previous_action"):
        assert token in guide
    for mode in ("velocity_command", "joint_position", "residual_baseline"):
        assert mode in guide
    for scenario in ("flat_ground", "low_friction", "slope", "rough_heightfield", "push_disturbance"):
        assert scenario in guide
    for artifact in ARTIFACTS:
        assert artifact in guide
    for metric_token in (
        "command tracking",
        "stability",
        "action quality",
        "contact/terrain proxies",
        "reward `0.0`",
        "position-servo",
    ):
        assert metric_token in guide_lower


def test_controller_family_matrix_required_content():
    guide = GUIDE.read_text(encoding="utf-8")

    assert "| Controller family | Status now | Argus hook/seam | Why supported/deferred | Prerequisite to unlock | R&D rationale link |" in guide
    for family in FAMILIES:
        assert family in guide
    for token in (
        "supported now",
        "registered placeholder unavailable",
        "deferred/no runnable v4.0 implementation",
        "analytical_trot",
        "residual_policy",
        "direct_policy",
        "mpc",
        "wbc",
    ):
        assert token in guide


def test_locomotion_rationale_link_and_current_method():
    guide = GUIDE.read_text(encoding="utf-8")

    assert "outputs/locomotion-rd-systems.md" in guide
    assert "docs/adr/0019-benchmark-locomotion-before-adding-new-controller-families.md" in guide
    assert "Current Argus locomotion is analytical trot plus MuJoCo position actuators." in guide
    for unsupported_claim in (
        "does not ship trained RL policies",
        "torque-control locomotion",
        "perception-conditioned locomotion",
    ):
        assert unsupported_claim in guide


def test_residual_policy_documentation_matches_registry_action_mode():
    from src.locomotion.actions import available_action_modes
    from src.locomotion.controllers import ControllerRegistry

    guide = GUIDE.read_text(encoding="utf-8")
    entries = {entry["name"]: entry for entry in ControllerRegistry.list_controllers()}
    residual = entries["residual_policy"]
    action_mode = residual["capabilities"]["action_mode"]

    assert residual["available"] is False
    assert action_mode == "residual_baseline"
    assert action_mode in available_action_modes()
    assert (
        f"Controller id `residual_policy`; residual-over-baseline seam via `{action_mode}` action mode"
        in guide
    )


def test_wbc_documentation_matches_registry_deferred_action_contract():
    from src.locomotion.actions import available_action_modes
    from src.locomotion.controllers import ControllerRegistry

    guide = GUIDE.read_text(encoding="utf-8")
    entries = {entry["name"]: entry for entry in ControllerRegistry.list_controllers()}
    wbc = entries["wbc"]
    capabilities = wbc["capabilities"]
    model_requirements = capabilities["model_requirements"]

    assert wbc["available"] is False
    assert capabilities["action_mode"] == "undefined_deferred"
    assert capabilities["action_mode"] not in available_action_modes()
    assert model_requirements["action_contract"] == "undefined_deferred"
    assert model_requirements["env_action_mode"] is None
    assert "torque_or_joint_position" not in guide
    assert (
        "Controller id `wbc`; future action contract `undefined_deferred` "
        "(not a v4.0 env action mode)"
        in guide
    )



def test_locomotion_benchmark_guide_states_evaluator_action_mode_contract():
    guide = GUIDE.read_text(encoding="utf-8")

    assert "argus eval-locomotion currently runs `velocity_command`" in guide
    assert "joint_position" in guide
    assert "residual_baseline" in guide
    assert "env-supported seams" in guide
    assert "fail fast" in guide



def test_doc_guard_source_stays_content_only():
    source = Path(__file__).read_text(encoding="utf-8")
    comparison_literals = {SMOKE_COMMAND, "uv run", "eval-locomotion --controller"}
    scrubbed = source
    for literal in comparison_literals:
        scrubbed = scrubbed.replace(literal, "")

    forbidden = ("sub" + "process", "uv" + " run", "eval-locomotion" + " --controller", "Argus" + "Go2Env")
    for token in forbidden:
        assert token not in scrubbed
