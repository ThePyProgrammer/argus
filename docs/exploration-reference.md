# Exploration reference area

The reference extractor builds a fixed evaluation denominator from compiled MuJoCo collision geometry. It is implemented separately from the analytical benchmark fixtures and is not connected to the robot's planner or dashboard coverage field.

## Inspect the fixtures

From the repository root:

```bash
uv run python scripts/inspect_exploration_reference.py
uv run python scripts/inspect_exploration_reference.py --scenario connected_rooms --probe 0 0 --probe 7 0
```

The script compares the compiled and analytical masks before exporting anything. By default, each layout's output goes under `outputs/exploration-reference/<scenario>/`:

| File | Content |
| --- | --- |
| `reference.svg` | Reference area, disconnected free cells, fixed anchor, and accepted/rejected spawn markers. |
| `reference.json` | Grid configuration, geometry/reference hashes, area, and spawn diagnostics. |
| `reference.npz` | Immutable reference and free-space masks serialized as boolean arrays. |
| `source.json` | Scenario, XML, and metadata hashes from the fixture loader. |

Use `--resolution 0.05` for the finer validated grid or `--output-root PATH` to choose another output directory. Generated files in the default directory are ignored by Git. Out-of-bounds spawn markers are drawn at the nearest image edge; their tooltips and JSON retain the actual coordinates.

## Geometry contract

The extractor accepts a static environment model before robots are inserted. It supports boxes at arbitrary 3D rotations and one explicitly named, upward-facing horizontal box or plane floor. Nested body transforms are resolved through MuJoCo forward kinematics. Movable or mocap bodies, flexes, explicit contact pairs/exclusions, and other collidable shapes are rejected. This is not yet a mesh or general terrain extractor.

Each candidate robot center carries a world-aligned clearance prism, initially 0.40 m in each horizontal direction and 0.60 m tall. A separating-axis intersection test checks the prism against actual oriented collision boxes. Geometry above the clearance height does not block passage. Non-colliding decorations are ignored using the configured robot collision bitmasks. Collision margins and gait dynamics are not modeled; the contract describes geometric clearance.

Bounds are explicit and finite, including for an infinite MuJoCo floor plane. The whole prism must stay inside those bounds and be supported by the named floor. Floor height comes from the compiled geometry. Grid cells are sampled at their centers; this is a discrete center-position reference, not a claim that every point inside each cell is navigable.

The fixed component anchor selects a four-connected region. Connections between cell centers also require swept-prism clearance, so a thin wall between two free centers cannot join rooms. Spawn checks validate physical clearance, cell membership, and a conservative connection to the cell center. Neither a sampled spawn nor an episode outcome can change the denominator.

## Python interface

```python
from src.exploration.evaluation.scenarios import load_scenario

scene = load_scenario("connected_rooms")
reference = scene.compiled_reference()
print(reference.metadata())
print(reference.check_spawn(0, 0))
```

For another supported static environment, call `build_reference_grid(model, ReferenceConfig(...))` from [exploration_reference.py](../src/metrics/exploration_reference.py). The returned masks and geometry are immutable snapshots. Geometry hashes capture the compiled collision shapes; reference hashes also include configuration, generator version, and the selected mask. Full experiment manifests will additionally record source assets, code, and environment versions.

Validation compares all three fixture masks at 0.10 m and 0.05 m with independently computed analytical areas. Further tests cover rotated/tilted obstacles, MuJoCo contact agreement, translated geometry, narrow doors, thin walls, disconnected rooms, floor support, height clearance, and diagnostics. The [measurement collectors](exploration-measurements.md) now use this reference for camera-based coverage. Episode integration is next in the [execution plan](plans/exploration-evaluation.md).
