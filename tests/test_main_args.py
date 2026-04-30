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
from types import SimpleNamespace


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
    monkeypatch.setattr(main_module, "configure_mcp", lambda coordinator, robot_ids: None)
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
