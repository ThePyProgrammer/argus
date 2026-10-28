import io
from pathlib import Path
import xml.etree.ElementTree as ET

import mujoco
import numpy as np
import trimesh

from src.bridge.scene_assets import ensure_colored_scene, recover_office_assets
from src.bridge.scene_builder import build_two_robot_office_scene
from src.metrics.mujoco_gt import MuJoCoGTExtractor


def test_colored_scene_uses_xml_colors_and_excludes_collision_meshes(tmp_path):
    source = trimesh.Scene()
    source.add_geometry(trimesh.creation.box(), node_name="wall")
    source.add_geometry(trimesh.creation.box(), node_name="wall_convex_1")
    glb = tmp_path / "scene.glb"
    source.export(glb)
    xml = tmp_path / "office.xml"
    xml.write_text('''<mujoco><asset><material name="red" rgba="1 0 0 1"/></asset>
      <worldbody><geom mesh="wall" material="red"/></worldbody></mujoco>''')
    output = tmp_path / "scene_colored.glb"

    ensure_colored_scene(glb, xml, output)

    colored = trimesh.load_scene(output, process=False)
    assert list(colored.graph.nodes_geometry) == ["wall"]
    mesh = next(iter(colored.geometry.values()))
    np.testing.assert_array_equal(mesh.visual.face_colors[0], [255, 0, 0, 255])
    original = output.read_bytes()
    ensure_colored_scene(glb, xml, output)
    assert output.read_bytes() == original


def test_recovery_uses_node_names_and_transforms_without_changing_collisions(tmp_path):
    scene = trimesh.Scene()
    transform = trimesh.transformations.translation_matrix([1, 2, 3])
    scene.add_geometry(
        trimesh.creation.box(), node_name="office_wall", geom_name="different_name",
        transform=transform,
    )
    glb = tmp_path / "scene.glb"
    scene.export(glb)
    root = ET.fromstring('''<mujoco><compiler/><asset>
      <mesh name="office_wall" file="office_wall.obj"/>
      <texture name="wall_texture" file="wall.png" type="2d"/>
      <material name="wall" texture="wall_texture" rgba="0.5 0.4 0.3 1"/>
      </asset><worldbody><body name="wall_body" euler="1.5708 0 0">
      <geom type="mesh" mesh="office_wall" contype="1" conaffinity="0"/>
      </body></worldbody></mujoco>''')
    original_body = ET.tostring(root.find("worldbody"))
    assets = {"office_wall.obj": b"version https://git-lfs.github.com/spec/v1\n"}

    recover_office_assets(root, assets, glb)

    recovered = trimesh.load(io.BytesIO(assets["office_wall.obj"]), file_type="obj")
    np.testing.assert_allclose(recovered.bounds, [[0.5, 1.5, 2.5], [1.5, 2.5, 3.5]])
    assert ET.tostring(root.find("worldbody")) == original_body
    assert root.find("asset/texture") is None
    assert root.find("asset/material").attrib == {"name": "wall", "rgba": "0.5 0.4 0.3 1"}


def test_available_assets_do_not_require_glb(tmp_path):
    root = ET.fromstring('<mujoco><asset><mesh name="wall" file="wall.obj"/></asset></mujoco>')
    assets = {"wall.obj": b"original mesh"}
    recover_office_assets(root, assets, tmp_path / "absent.glb")
    assert assets["wall.obj"] == b"original mesh"
    assert root.find("asset/mesh").get("inertia") is None


def test_bundled_office_compiles_with_collisions_and_ground_truth():
    project = Path(__file__).resolve().parents[2]
    xml, assets = build_two_robot_office_scene(
        str(project / "models" / "unitree_go2"), {"robot_a": (0, 0, 0.3)},
    )
    model = mujoco.MjModel.from_xml_string(xml, assets)
    assert model.nmesh > 1200
    body = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "body_BezierCurve_009_SwivlChair")
    assert body > 0
    assert np.count_nonzero(model.geom_contype) > 1000
    data = mujoco.MjData(model)
    for _ in range(10):
        mujoco.mj_step(model, data)
    assert np.isfinite(data.qpos).all()
    gt = MuJoCoGTExtractor(project / "data/scenes/scene_office1_gt.yaml", model, data)
    assert "chair" in gt.all_classes()
