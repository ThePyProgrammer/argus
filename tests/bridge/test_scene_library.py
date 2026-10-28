import numpy as np
import pytest
import mujoco
from src.bridge.scene_library import PROMPT_SCENES, scene_geometry, scene_xml, build_library_model, default_positions, open_floor
from src.bridge.platforms.go2 import Go2Platform

@pytest.mark.parametrize('scene', PROMPT_SCENES)
def test_every_library_scene_compiles_with_robots_and_matches_preview(scene):
    preview = scene_geometry(scene)
    positions = default_positions(scene, ['robot_a', 'robot_b'], .3)
    assert all(open_floor(scene, *pos[:2]) for pos in positions.values())
    model = build_library_model(Go2Platform(), positions, scene)
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    assert model.nu == 24
    for geom in preview['geoms']:
        gid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, 'env_' + geom['name'])
        assert gid >= 0
        if not geom['floor']:  # infinite physics plane is clipped only for map display
            np.testing.assert_allclose(data.geom_xpos[gid], geom['position'], atol=1e-7)
            np.testing.assert_allclose(data.geom_xmat[gid], geom['rotation'], atol=1e-7)
            np.testing.assert_allclose(model.geom_size[gid], geom['size'], atol=1e-7)
    mujoco.mj_step(model, data)
    assert np.isfinite(data.qpos).all()


def test_spawn_validation_rejects_furniture_and_outside_map():
    assert not open_floor('coffee_shop', 0, 0)
    assert not open_floor('gym', 100, 100)


def test_source_normalization_keeps_workbench_tools_dynamic():
    model = mujoco.MjModel.from_xml_string(scene_xml('workbench'))
    joint = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, 'hammer_free')
    assert model.jnt_type[joint] == mujoco.mjtJoint.mjJNT_FREE
    body = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, 'hammer')
    assert model.body_parentid[body] == 0


def test_low_rugs_are_selectable_but_tables_are_not():
    geoms = scene_geometry('gym')['geoms']
    assert any(g['walkable'] and not g['floor'] for g in geoms)
    assert not next(g for g in scene_geometry('coffee_shop')['geoms'] if g['name'] == 'counter_top')['walkable']
