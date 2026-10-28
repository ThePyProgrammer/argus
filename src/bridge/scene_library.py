"""Bundled scene catalog and a shared MuJoCo-derived preview representation."""
from functools import lru_cache
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np

SCENE_DIR = Path(__file__).resolve().parents[2] / 'data' / 'scene_library' / 'prompt'
PROMPT_SCENES = {
    'chemistry_lab': ('Chemistry lab', 'Lab benches, glassware and equipment'),
    'chess': ('Chess room', 'Chess table and surrounding furniture'),
    'coffee_shop': ('Coffee shop', 'Espresso counter, grinder and seating'),
    'gym': ('Gym', 'Exercise equipment and free weights'),
    'living_room': ('Living room', 'Sofa, tables and household objects'),
    'prompt_office': ('Modern office', 'Desks, chairs and movable office props'),
    'playground': ('Playground', 'Outdoor play equipment'),
    'restaurant': ('Restaurant', 'Dining tables and restaurant furniture'),
    'workbench': ('Workbench', 'Workshop bench and loose tools'),
}
SCENES = {'flat': ('Open floor', 'Open checkerboard test environment'),
          'office': ('Argus office', 'Original scanned office environment'), **PROMPT_SCENES}


def require_scene(scene: str) -> str:
    if scene not in SCENES:
        raise ValueError(f'Unknown scene: {scene}')
    return scene


def catalog():
    return [{'id': key, 'name': value[0], 'description': value[1],
             'source': 'mujoco-scene-editor' if key in PROMPT_SCENES else 'Argus'}
            for key, value in SCENES.items()]


@lru_cache(maxsize=16)
def scene_xml(scene: str) -> str:
    require_scene(scene)
    if scene not in PROMPT_SCENES:
        raise ValueError('Only bundled prompt scenes have standalone MJCF')
    name = 'office' if scene == 'prompt_office' else scene
    root = ET.parse(SCENE_DIR / f'scene_{name}.xml').getroot()
    for i, geom in enumerate(root.find('worldbody').iter('geom')):
        if not geom.get('name'):
            geom.set('name', f'argus_geom_{i}')
    # Upstream office capsules specify both pos and fromto (invalid MJCF).
    # fromto already contains their complete placement.
    for geom in root.iter('geom'):
        if 'fromto' in geom.attrib:
            geom.attrib.pop('pos', None)
    # Upstream workbench puts free bodies under an identity-transform bench.
    # Promote them to world children, preserving their poses and free motion.
    if scene == 'workbench':
        world = root.find('worldbody')
        bench = world.find("body[@name='bench']")
        assert bench.get('pos') == '0 0 0' and not any(k in bench.attrib for k in ('quat', 'euler', 'axisangle'))
        for body in list(bench.findall('body')):
            if body.find('freejoint') is not None:
                bench.remove(body)
                world.append(body)
    return ET.tostring(root, encoding='unicode')


@lru_cache(maxsize=16)
def scene_geometry(scene: str) -> dict:
    """Return initial world-space primitives, including resolved MJCF defaults."""
    require_scene(scene)
    if scene == 'flat':
        return {'geoms': [{'name': 'floor', 'type': 0, 'size': [15, 15, .05],
                         'position': [0, 0, 0], 'rotation': np.eye(3).ravel().tolist(),
                         'rgba': [.18, .23, .20, 1], 'floor': True}], 'bounds': [-15, -15, 15, 15]}
    import mujoco
    model = mujoco.MjModel.from_xml_string(scene_xml(scene))
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    geoms = []
    bounds = None
    for i in range(model.ngeom):
        kind = int(model.geom_type[i])
        pos, size = data.geom_xpos[i], model.geom_size[i]
        floor = bool(kind == 0 and abs(pos[2]) < .1)
        if floor:
            bounds = [float(pos[0]-size[0]), float(pos[1]-size[1]), float(pos[0]+size[0]), float(pos[1]+size[1])]
        walkable = bool(floor or (kind == 6 and abs(data.geom_xmat[i][8]) > .99 and -.01 <= pos[2]+size[2] <= .06))
        geoms.append({'name': mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, i) or f'geom_{i}',
                      'type': kind, 'size': size.tolist(), 'position': pos.tolist(),
                      'rotation': data.geom_xmat[i].tolist(), 'rgba': model.geom_rgba[i].tolist(), 'floor': floor, 'walkable': walkable})
    if bounds is None:
        raise ValueError(f'Scene {scene} has no ground plane')
    # Infinite MuJoCo planes often have huge display sizes. Keep the selectable
    # map focused on the authored furniture plus a walkable perimeter.
    points = [np.array(g['position'][:2]) + sign * _half_extents(g)[:2]
              for g in geoms if not g['floor'] for sign in (-1, 1)]
    if points:
        low, high = np.min(points, axis=0) - 2, np.max(points, axis=0) + 2
        bounds = [max(bounds[0], float(low[0])), max(bounds[1], float(low[1])),
                  min(bounds[2], float(high[0])), min(bounds[3], float(high[1]))]
        for geom in geoms:
            if geom['floor']:
                geom['position'][:2] = [(bounds[0]+bounds[2])/2, (bounds[1]+bounds[3])/2]
                geom['size'][:2] = [(bounds[2]-bounds[0])/2, (bounds[3]-bounds[1])/2]
    return {'geoms': geoms, 'bounds': bounds}


def _half_extents(geom):
    size = np.array(geom['size'])
    kind = geom['type']
    if kind == 2:
        size = np.repeat(size[0], 3)
    elif kind in (3, 5):
        size = np.array([size[0], size[0], size[1] + (size[0] if kind == 3 else 0)])
    return np.abs(np.array(geom['rotation']).reshape(3, 3)) @ size


def open_floor(scene: str, x: float, y: float, radius: float = .35) -> bool:
    """Conservative robot clearance against the authored scene's primitive bounds."""
    if scene == 'office':
        return True  # legacy scanned map uses its floor raycast
    geometry = scene_geometry(scene)
    x0, y0, x1, y1 = geometry['bounds']
    if not (x0 + radius <= x <= x1 - radius and y0 + radius <= y <= y1 - radius):
        return False
    for geom in geometry['geoms']:
        if geom['floor']:
            continue
        extent = _half_extents(geom)
        pos = np.array(geom['position'])
        if pos[2] + extent[2] < .06 or pos[2] - extent[2] > 1.5:
            continue
        if abs(x - pos[0]) < extent[0] + radius and abs(y - pos[1]) < extent[1] + radius:
            return False
    return True


def default_positions(scene: str, robot_ids, height: float, radius: float = .35):
    from src.coordination.spawn import generate_spawn_positions
    require_scene(scene)
    if scene in ('office', 'flat'):
        return generate_spawn_positions(tuple(robot_ids), scene, height)
    x0, y0, x1, y1 = scene_geometry(scene)['bounds']
    candidates = [(float(x), float(y)) for x in np.arange(x0 + radius + .2, x1 - radius, max(1., 2*radius))
                  for y in np.arange(y0 + radius + .2, y1 - radius, max(1., 2*radius)) if open_floor(scene, x, y, radius)]
    chosen = []
    for rid in robot_ids:
        available = [p for p in candidates if all(np.hypot(p[0]-q[0], p[1]-q[1]) >= 2*radius for q in chosen)]
        if not available:
            raise ValueError('Not enough clear floor space for this robot count')
        point = min(available, key=lambda p: p[0]**2+p[1]**2) if not chosen else max(available, key=lambda p: min((p[0]-q[0])**2+(p[1]-q[1])**2 for q in chosen))
        chosen.append(point)
    return {rid: (*point, height) for rid, point in zip(robot_ids, chosen)}


def build_library_model(platform, positions, scene: str):
    """Attach authored scene to the robot model without sharing default classes."""
    import mujoco
    from src.bridge.scene_builder import build_multi_robot_scene
    xml, assets = build_multi_robot_scene(platform, positions)
    root = ET.fromstring(xml)
    world = root.find('worldbody')
    world.remove(world.find("geom[@name='floor']"))
    robot_spec = mujoco.MjSpec.from_string(ET.tostring(root, encoding='unicode'), assets=assets)
    environment = mujoco.MjSpec.from_string(scene_xml(scene))
    robot_spec.attach(environment, prefix='env_', frame=robot_spec.worldbody.add_frame())
    return robot_spec.compile()
