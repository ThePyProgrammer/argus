"""DET-METRICS-03: --labeled-eval-set CLI flag reservation test.

Per CONTEXT D-10: the flag is parsed but passing it MUST raise
NotImplementedError with the exact message
"Labeled eval set ingestion arrives in a future milestone".

Revision 2026-04-15 (WARNING 5): subprocess invocation is the ONLY
acceptable path for this test — any argument-parsing-only fallback would
silently skip verification of the actual NotImplementedError raise.
Subprocess timeout is generous (60s) for an argparse + early-return code
path; ``main()`` checks ``args.labeled_eval_set`` and raises BEFORE any
heavy init (coordinator / bridge / scene loading).
"""
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock


class _FakePlatformMetadata:
    spawn_height = 0.73

    def to_wire(self):
        return {"name": "fake_go2", "display_name": "Fake GO2 Test Platform"}


class _FakeBridge:
    platform_metadata = _FakePlatformMetadata()

    def __init__(self, config):
        self.config = config

    def stop(self):
        pass


class _FakeCoordinator:
    restart_requested = False
    restart_positions = None
    _restarting = False

    def __init__(self, bridge, robots, config):
        self.bridge = bridge
        self.robots = robots
        self.config = config

    def handle_command(self, command):
        pass

    def reset_merger(self):
        pass

    def set_viz(self, viz):
        self.viz = viz

    def set_freeze_motion(self, frozen):
        self.frozen = frozen

    def run(self, max_steps):
        return SimpleNamespace(terminated_reason="test", total_steps=0, merge_count=0)

    def request_stop(self):
        pass


def test_web_mode_passes_bridge_platform_metadata_to_create_app(monkeypatch):
    """Production startup should wire selected platform metadata into WS app setup."""
    import src.main as main_module

    captured = {}
    robot_ids = ["robot_a", "robot_b"]
    platform_metadata = _FakePlatformMetadata()
    platform_wire = platform_metadata.to_wire()

    def fake_create_app(robot_ids_arg, **kwargs):
        captured["robot_ids"] = robot_ids_arg
        captured["platform_metadata"] = kwargs.get("platform_metadata")
        return SimpleNamespace(state=SimpleNamespace()), SimpleNamespace()

    def fake_generate_spawn_positions(ids, scene, *, spawn_height):
        captured["spawn_height"] = spawn_height
        return {rid: (0.0, 0.0, spawn_height) for rid in ids}

    monkeypatch.setattr(main_module, "generate_robot_ids", lambda n: robot_ids)
    monkeypatch.setattr(main_module, "generate_spawn_positions", fake_generate_spawn_positions)
    def fake_create_platform(name, **kwargs):
        captured["platform_name"] = name
        captured["platform_config"] = kwargs
        return SimpleNamespace(metadata=platform_metadata)

    monkeypatch.setattr(main_module, "create_platform", fake_create_platform)
    monkeypatch.setattr(
        main_module,
        "MultiRobotConfig",
        lambda **kwargs: SimpleNamespace(**kwargs, resolution=(640, 480)),
    )
    monkeypatch.setattr(main_module, "MultiRobotBridge", _FakeBridge)
    monkeypatch.setattr(
        main_module.CameraIntrinsics,
        "from_fov",
        staticmethod(lambda width, height: SimpleNamespace(width=width, height=height)),
    )
    monkeypatch.setattr(
        main_module.RobotInstance,
        "create",
        staticmethod(lambda **kwargs: SimpleNamespace(**kwargs)),
    )
    monkeypatch.setattr(main_module, "Coordinator", _FakeCoordinator)
    mcp_stub = SimpleNamespace(configure=lambda coordinator, robot_ids: None, mcp_endpoint=None)
    monkeypatch.setitem(sys.modules, "src.mcp.server", mcp_stub)
    monkeypatch.setattr(main_module, "create_app", fake_create_app)
    monkeypatch.setattr(main_module.subprocess, "run", lambda *args, **kwargs: None)

    uvicorn_stub = SimpleNamespace(run=lambda *args, **kwargs: None)
    monkeypatch.setitem(sys.modules, "uvicorn", uvicorn_stub)

    args = SimpleNamespace(
        scene="flat",
        num_robots=2,
        multi_boot_steps=0,
        explore_rescan_distance=2.0,
        octomap_resolution=0.1,
        multi_max_steps=0,
        static=False,
        port=8000,
    )

    main_module.run_web_mode(args)

    assert captured["platform_name"] == "go2"
    assert captured["platform_config"] == {}
    assert captured["robot_ids"] == robot_ids
    assert captured["spawn_height"] == platform_metadata.spawn_height
    assert captured["platform_metadata"] == {rid: platform_wire for rid in robot_ids}


def test_web_mode_registers_builtin_slam_backends_before_robot_creation(monkeypatch):
    """Web mode should have the default ICP backend registered before RobotInstance.create."""
    import src.main as main_module
    from src.slam.registry import SLAMRegistry

    SLAMRegistry._clear()
    captured = {}
    robot_ids = ["robot_a"]
    platform_metadata = _FakePlatformMetadata()

    def fake_create_app(robot_ids_arg, **kwargs):
        return SimpleNamespace(state=SimpleNamespace()), SimpleNamespace()

    def fake_robot_create(**kwargs):
        captured["backends_at_robot_create"] = list(SLAMRegistry._backends)
        return SimpleNamespace(**kwargs)

    monkeypatch.setattr(main_module, "generate_robot_ids", lambda n: robot_ids)
    monkeypatch.setattr(
        main_module,
        "generate_spawn_positions",
        lambda ids, scene, *, spawn_height: {rid: (0.0, 0.0, spawn_height) for rid in ids},
    )
    monkeypatch.setattr(
        main_module,
        "create_platform",
        lambda name, **kwargs: SimpleNamespace(metadata=platform_metadata),
    )
    monkeypatch.setattr(
        main_module,
        "MultiRobotConfig",
        lambda **kwargs: SimpleNamespace(**kwargs, resolution=(640, 480)),
    )
    monkeypatch.setattr(main_module, "MultiRobotBridge", _FakeBridge)
    monkeypatch.setattr(
        main_module.CameraIntrinsics,
        "from_fov",
        staticmethod(lambda width, height: SimpleNamespace(width=width, height=height)),
    )
    monkeypatch.setattr(main_module.RobotInstance, "create", staticmethod(fake_robot_create))
    monkeypatch.setattr(main_module, "Coordinator", _FakeCoordinator)
    mcp_stub = SimpleNamespace(configure=lambda coordinator, robot_ids: None, mcp_endpoint=None)
    monkeypatch.setitem(sys.modules, "src.mcp.server", mcp_stub)
    monkeypatch.setattr(main_module, "create_app", fake_create_app)
    monkeypatch.setattr(main_module.subprocess, "run", lambda *args, **kwargs: None)

    uvicorn_stub = SimpleNamespace(run=MagicMock())
    monkeypatch.setitem(sys.modules, "uvicorn", uvicorn_stub)

    args = SimpleNamespace(
        scene="flat",
        num_robots=1,
        multi_boot_steps=0,
        explore_rescan_distance=2.0,
        octomap_resolution=0.1,
        multi_max_steps=0,
        static=False,
        port=8000,
    )

    try:
        main_module.run_web_mode(args)
    finally:
        SLAMRegistry._clear()
        from src.slam.backends import register_builtin_backends

        register_builtin_backends()

    assert "icp" in captured["backends_at_robot_create"]


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


def test_eval_locomotion_parser_uses_none_for_scalar_overrides_until_explicit(monkeypatch):
    """Matrix-config scalars must survive unless explicit CLI overrides are present."""
    import src.main as main_module

    monkeypatch.setattr(sys, "argv", ["argus", "eval-locomotion"])

    args = main_module.parse_args()

    assert args.action_mode is None
    assert args.max_episode_steps is None
    assert args.sim_steps_per_frame is None
    assert args.heightfield_size is None
    assert args.output_root == "outputs/locomotion-evals"


def test_eval_locomotion_help_lists_artifact_flags():
    """LOC-EVAL-01 D-01 D-02 D-03: help is quiet and artifact-focused."""
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.main",
            "eval-locomotion",
            "--help",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )

    combined = proc.stdout + proc.stderr
    assert proc.returncode == 0, combined
    for expected in (
        "eval-locomotion",
        "--controller",
        "--scenario",
        "--seed",
        "--matrix-config",
        "--from-run-dir",
        "--output-root",
        "--verbose",
    ):
        assert expected in combined


def test_eval_locomotion_help_lists_action_mode_contract():
    """eval-locomotion help must distinguish runnable and deferred action modes."""
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.main",
            "eval-locomotion",
            "--help",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )

    combined = proc.stdout + proc.stderr
    assert proc.returncode == 0, combined
    assert "--action-mode" in combined
    assert "velocity_command is the evaluator-runnable mode" in combined
    assert "joint_position and residual_baseline are env-supported seams" in combined


def test_eval_locomotion_matrix_config_action_mode_fails_fast_before_artifacts(tmp_path):
    """Unsupported matrix-config action modes must reach evaluation validation."""
    config_path = tmp_path / "matrix.json"
    output_root = tmp_path / "out"
    config_path.write_text(
        """
{
  "controllers": ["analytical_trot"],
  "scenarios": ["flat_ground"],
  "seeds": [101],
  "action_mode": "joint_position",
  "max_episode_steps": 2,
  "sim_steps_per_frame": 3,
  "heightfield_size": 4
}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.main",
            "eval-locomotion",
            "--matrix-config",
            str(config_path),
            "--output-root",
            str(output_root),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )

    combined = proc.stdout + proc.stderr
    assert proc.returncode != 0, combined
    assert "argus eval-locomotion currently runs action_mode='velocity_command'" in combined
    assert "requested action_mode='joint_position'" in combined
    assert not output_root.exists()


def test_eval_locomotion_matrix_config_scalars_are_honored_without_cli_overrides(monkeypatch):
    """Absent CLI scalars should preserve loaded matrix-config scalar values."""
    import src.main as main_module

    captured = {}

    class FakeEvaluationMatrix:
        def __init__(
            self,
            *,
            controllers=("analytical_trot",),
            scenarios=("flat_ground",),
            seeds=(101,),
            action_mode="velocity_command",
            max_episode_steps=500,
            sim_steps_per_frame=10,
            heightfield_size=16,
        ):
            self.controllers = tuple(controllers)
            self.scenarios = tuple(scenarios)
            self.seeds = tuple(seeds)
            self.action_mode = action_mode
            self.max_episode_steps = max_episode_steps
            self.sim_steps_per_frame = sim_steps_per_frame
            self.heightfield_size = heightfield_size

    class FakeEvaluationRunConfig:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    def fake_load_matrix_config(path):
        captured["path"] = path
        return FakeEvaluationMatrix(
            action_mode="residual_baseline",
            max_episode_steps=7,
            sim_steps_per_frame=8,
            heightfield_size=9,
        )

    def fake_run_evaluation_matrix(matrix, config):
        captured["matrix"] = matrix
        captured["config"] = config
        return SimpleNamespace(
            run_dir=Path("/tmp/fake-run"),
            episode_rows=[],
            exit_code=0,
        )

    fake_module = SimpleNamespace(
        EvaluationMatrix=FakeEvaluationMatrix,
        EvaluationRunConfig=FakeEvaluationRunConfig,
        load_matrix_config=fake_load_matrix_config,
        regenerate_comparison=lambda run_dir: None,
        run_evaluation_matrix=fake_run_evaluation_matrix,
    )
    monkeypatch.setitem(sys.modules, "src.locomotion.evaluation", fake_module)
    args = SimpleNamespace(
        from_run_dir=None,
        matrix_config="matrix.json",
        controller=None,
        scenario=None,
        seed=None,
        action_mode=None,
        max_episode_steps=None,
        sim_steps_per_frame=None,
        heightfield_size=None,
        output_root="outputs/locomotion-evals",
        max_matrix_runs=1000,
        allow_locomotion_failures=False,
        verbose=False,
    )

    assert main_module.run_eval_locomotion_mode(args) == 0

    matrix = captured["matrix"]
    assert matrix.action_mode == "residual_baseline"
    assert matrix.max_episode_steps == 7
    assert matrix.sim_steps_per_frame == 8
    assert matrix.heightfield_size == 9


def test_eval_locomotion_explicit_cli_scalars_override_matrix_config(monkeypatch):
    """Explicit CLI scalars should override loaded matrix-config scalar values."""
    import src.main as main_module

    captured = {}

    class FakeEvaluationMatrix:
        def __init__(
            self,
            *,
            controllers=("analytical_trot",),
            scenarios=("flat_ground",),
            seeds=(101,),
            action_mode="velocity_command",
            max_episode_steps=500,
            sim_steps_per_frame=10,
            heightfield_size=16,
        ):
            self.controllers = tuple(controllers)
            self.scenarios = tuple(scenarios)
            self.seeds = tuple(seeds)
            self.action_mode = action_mode
            self.max_episode_steps = max_episode_steps
            self.sim_steps_per_frame = sim_steps_per_frame
            self.heightfield_size = heightfield_size

    class FakeEvaluationRunConfig:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    def fake_load_matrix_config(path):
        return FakeEvaluationMatrix(
            action_mode="residual_baseline",
            max_episode_steps=7,
            sim_steps_per_frame=8,
            heightfield_size=9,
        )

    def fake_run_evaluation_matrix(matrix, config):
        captured["matrix"] = matrix
        return SimpleNamespace(
            run_dir=Path("/tmp/fake-run"),
            episode_rows=[],
            exit_code=0,
        )

    fake_module = SimpleNamespace(
        EvaluationMatrix=FakeEvaluationMatrix,
        EvaluationRunConfig=FakeEvaluationRunConfig,
        load_matrix_config=fake_load_matrix_config,
        regenerate_comparison=lambda run_dir: None,
        run_evaluation_matrix=fake_run_evaluation_matrix,
    )
    monkeypatch.setitem(sys.modules, "src.locomotion.evaluation", fake_module)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "argus",
            "eval-locomotion",
            "--matrix-config",
            "ignored.json",
            "--action-mode",
            "velocity_command",
            "--max-episode-steps",
            "11",
            "--sim-steps-per-frame",
            "12",
            "--heightfield-size",
            "13",
        ],
    )
    args = main_module.parse_args()

    assert main_module.run_eval_locomotion_mode(args) == 0

    matrix = captured["matrix"]
    assert matrix.action_mode == "velocity_command"
    assert matrix.max_episode_steps == 11
    assert matrix.sim_steps_per_frame == 12
    assert matrix.heightfield_size == 13


def test_eval_locomotion_is_not_a_control_choice():
    """LOC-EVAL-01 D-01: offline evaluation is not a --control runtime mode."""
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.main",
            "--help",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )

    combined = proc.stdout + proc.stderr
    assert proc.returncode == 0, combined
    control_lines = [line for line in combined.splitlines() if "--control" in line or "teleop" in line]
    assert control_lines, combined
    assert all("eval-locomotion" not in line for line in control_lines)


def test_labeled_eval_set_flag_raises_not_implemented(tmp_path):
    """--labeled-eval-set <path> must raise NotImplementedError + exit non-zero."""
    dummy = tmp_path / "eval.json"
    dummy.write_text("{}", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "src.main", "--labeled-eval-set", str(dummy)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    # Expect non-zero exit (Python raises → traceback → sys.exit(1)).
    assert proc.returncode != 0, (
        f"expected non-zero exit; stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )
    combined = proc.stdout + proc.stderr
    assert (
        "Labeled eval set ingestion arrives in a future milestone" in combined
    ), f"expected CONTEXT D-10 message in output; got: {combined!r}"
    # Sanity: the traceback must identify NotImplementedError (not some other
    # error raised by the argparse layer or an unrelated import).
    assert "NotImplementedError" in combined, (
        f"expected NotImplementedError in traceback; got: {combined!r}"
    )
