import sys
from types import SimpleNamespace

import src.main as main_module


def test_platform_arg_parses_agibot_x2(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["argus", "--platform", "agibot_x2"])

    args = main_module.parse_args()

    assert args.platform == "agibot_x2"


def test_platform_arg_parses_agibot_x2_custom_paths(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "argus",
            "--platform",
            "agibot_x2",
            "--x2-model-dir",
            "custom/path",
            "--x2-controller",
            "controller.pt",
        ],
    )

    args = main_module.parse_args()

    assert args.platform == "agibot_x2"
    assert args.x2_model_dir == "custom/path"
    assert args.x2_controller == "controller.pt"
    assert main_module._platform_config_from_args(args) == {
        "model_dir": "custom/path",
        "controller_path": "controller.pt",
    }


def test_platform_arg_defaults_to_go2(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["argus"])

    args = main_module.parse_args()

    assert args.platform == "go2"


def test_platform_config_is_empty_for_go2():
    args = SimpleNamespace(platform="go2", x2_model_dir="models/agibot_x2", x2_controller=None)

    assert main_module._platform_config_from_args(args) == {}


def test_platform_config_for_agibot_x2_includes_model_dir_only_by_default():
    args = SimpleNamespace(platform="agibot_x2", x2_model_dir="models/agibot_x2", x2_controller=None)

    assert main_module._platform_config_from_args(args) == {"model_dir": "models/agibot_x2"}


def test_platform_config_for_agibot_x2_includes_controller_when_provided():
    args = SimpleNamespace(
        platform="agibot_x2",
        x2_model_dir="models/agibot_x2",
        x2_controller="controllers/x2.pt",
    )

    assert main_module._platform_config_from_args(args) == {
        "model_dir": "models/agibot_x2",
        "controller_path": "controllers/x2.pt",
    }
