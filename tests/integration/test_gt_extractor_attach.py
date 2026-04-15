"""Phase 6 integration test — GT extractor end-to-end wiring.

Covers BLOCKER 2 (``attach_gt_extractor`` wires ``viz.gt_extractor`` from
a coordinator-bootstrap call) AND WARNING 6 (``scene_office1_gt.yaml``
resolves every body against ``scene_office1.xml``).

Uses REAL production artifacts — NOT test fixtures — because the only
regression we want to catch is scene/YAML drift at release time. Skip
honestly when either artifact is absent so this test is green in
release-gate environments that ship without the MuJoCo scene bundle.
"""
from __future__ import annotations

from pathlib import Path

import pytest

SCENE = Path("data/scenes/scene_office1.xml")
GT_YAML = Path("data/scenes/scene_office1_gt.yaml")


@pytest.mark.skipif(not SCENE.exists(), reason="scene_office1.xml not present")
@pytest.mark.skipif(not GT_YAML.exists(), reason="scene_office1_gt.yaml not present (Plan 07)")
def test_scene_office1_gt_mapping_resolves():
    """WARNING 6 fix: every body in scene_office1_gt.yaml resolves against scene_office1.xml.

    Also asserts each mapped body has at least one geom (required by
    MuJoCoGTExtractor which reads ``data.geom_xpos[first_geom_of_body]``
    per RESEARCH F1 — the body-origin accessor returns (0,0,0) for every
    body in this scene). Scene/YAML drift (a renamed body, a removed
    mesh) fires here.
    """
    import mujoco

    from src.metrics.mujoco_gt import MuJoCoGTExtractor

    model = mujoco.MjModel.from_xml_path(str(SCENE))
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)

    extractor = MuJoCoGTExtractor(GT_YAML, model, data)
    classes = extractor.all_classes()
    assert "chair" in classes, classes

    # Every mapped body resolves to a valid body_id (>=0) AND has at least
    # one geom. This is the scene/YAML drift guard.
    import yaml

    mapping = yaml.safe_load(GT_YAML.read_text(encoding="utf-8")) or {}
    for cls, bodies in mapping.items():
        for body_name in bodies:
            bid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, body_name)
            assert bid >= 0, f"class={cls} body={body_name} missing from scene"
            has_geom = any(
                int(model.geom_bodyid[g]) == bid for g in range(model.ngeom)
            )
            assert has_geom, (
                f"class={cls} body={body_name} has no geom for geom_xpos lookup"
            )


@pytest.mark.skipif(not SCENE.exists(), reason="scene_office1.xml not present")
@pytest.mark.skipif(not GT_YAML.exists(), reason="scene_office1_gt.yaml not present (Plan 07)")
def test_streaming_viz_attach_gt_extractor_end_to_end():
    """BLOCKER 2 fix: WebStreamingViz.attach_gt_extractor with real scene wires gt_extractor."""
    import mujoco

    from backend.web.connection_manager import ConnectionManager
    from backend.web.streaming_viz import WebStreamingViz

    model = mujoco.MjModel.from_xml_path(str(SCENE))
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)

    # Construct a minimal viz — Plan 08 signature: (connection_manager, robot_ids).
    viz = WebStreamingViz(
        connection_manager=ConnectionManager(),
        robot_ids=["robot_a", "robot_b"],
    )
    assert viz.gt_extractor is None, "pre-attach: gt_extractor must be None"

    viz.attach_gt_extractor(GT_YAML, model, data)

    assert viz.gt_extractor is not None, "post-attach: must be set (BLOCKER 2)"
    assert "chair" in viz.gt_extractor.all_classes(), viz.gt_extractor.all_classes()
