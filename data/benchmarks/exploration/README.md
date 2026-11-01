# Exploration benchmark fixtures

Three original, static MJCF layouts establish the first exploration study's geometry and initial-condition contract. Each XML has matching JSON metadata. Loading a scenario compiles its collision geometry and rejects disagreement with the metadata before any episode starts.

These assets are not yet connected to `argus --scene` or an `eval-exploration` command. Use the Python contract to inspect and sample them:

```python
from src.exploration.evaluation.scenarios import load_scenario

scene = load_scenario("connected_rooms")
print(scene.reference_metadata())
print(scene.sample(101).to_dict())
```

## Geometry and independent area checks

Every layout has interior bounds `[-6, -4, 6, 4]` meters, 0.20 m thick outer walls, a finite floor at Z=0, and 2 m high static obstacles. There are no movable props, external meshes, or texture downloads.

The analytical clearance model uses a world-aligned square with half extent 0.40 m, conservatively enclosing the platform's declared Go2 body at every heading. Its vertical envelope is 0.60 m; all non-floor geometry in these fixtures extends through that envelope. Touching a wall or obstacle fails the clearance check. This is a geometry approximation, not a locomotion guarantee.

At a 0.10 m resolution, cells are sampled at their centers. Rows increase with world Y, columns with world X. Four-connected flood fill from the fixed scenario anchor defines the reference component. The mask cannot depend on the sampled robot positions or on an exploration result.

| Layout | Analytical clear area | Reference cells at 0.10 m |
| --- | --- | --- |
| `branching_corridor` | `11.2 * 1.6 + 7.2 * 1.6 - 1.6 * 1.6 = 26.88 m2` | 2688 |
| `connected_rooms` | `11.2 * 7.2 - 5.6 * 1.0 - 9.6 * 1.0 + 1.0 * 1.0 = 66.44 m2` | 6644 |
| `cluttered_room` | `11.2 * 7.2 - 6 * 1.8 * 1.8 = 61.20 m2` | 6120 |

The corridor expression adds the horizontal and vertical arms and subtracts their common junction. The rooms expression subtracts the inflated internal wall segments and restores their shared crossing. Its 1.60 m doorways retain 0.80 m of center-position clearance. The clutter expression subtracts six disjoint inflated columns. Tests independently check these areas at both 0.10 m and 0.05 m resolution.

`reference_mask()` is a restricted analytical fixture oracle. `compiled_reference()` independently extracts the grid from compiled collision boxes, including rotated and tilted boxes. See the [reference-area guide](../../../docs/exploration-reference.md) for diagnostic exports and supported geometry. The camera observation collector remains a separate work item in the [execution plan](../../../docs/plans/exploration-evaluation.md).

## Initial conditions and provenance

Each layout supplies eight spawn locations and four cardinal body headings. Samples contain exactly `robot_a` and `robot_b`, a 0.30 m initial body height, and non-overlapping clearance envelopes. The loader rejects obstructed or disconnected pool points and pools with no feasible pair.

The seed is an integer in `[0, 2**32)`. Local NumPy generators use stream 0 for locations and stream 1 for headings; they do not consume global random state. Use the same sampled object for all methods and save its resolved positions/headings. The scenario hash covers the exact XML and JSON bytes. Reference metadata records the mask hash, grid convention, clearance parameters, component anchor, and reference version. Record the code revision and defaults alongside those fields in future run manifests.

Tests trace rays from the actual Go2 platform camera specification for every location and heading, checking that some floor is initially visible. They do not establish rendered depth accuracy, moving-robot visibility, or whether a controller can complete exploration. Those checks belong to later phases.

## Source and license metadata

The layouts were authored for Argus from simple geometric primitives. No third-party scene assets are included. JSON source fields record that origin. `license: NOASSERTION` means these fixtures do not introduce a separate license declaration; repository licensing is unchanged.
