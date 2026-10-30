# Argus

A robotics research workbench for simulating, observing, and evaluating multi-robot autonomy in MuJoCo.

Argus connects robot simulation, perception, mapping, exploration, and locomotion to a browser dashboard. Its goal is to make algorithms easier to compare under shared scenarios and measurable conditions.

## Current capabilities

| Area | Implemented |
| --- | --- |
| Simulation | Multiple Unitree Go2 robots in a shared scene, RGB/depth cameras, scene selection, and interactive spawn placement. |
| Mapping and exploration | ICP baseline, pluggable SLAM backends, voxel map merging, frontier exploration, A* planning, and region-biased coordination. |
| Perception | Configurable detectors, depth-based 3D boxes, object tracking, semantic maps, and detection metrics. Optional models require setup. |
| Browser dashboard | Live cameras, point clouds, voxels, meshes, trajectories, navigation controls, and a visual pipeline editor. |
| Locomotion evaluation | Analytical trot baseline, seeded terrain and disturbance scenarios, tracking/stability metrics, and structured exports. |
| Extensibility | Protocols and registries for backends, robot platforms, and controllers; MCP tools for simulation queries and commands. |

**Scope:** Simulation only, with CPU-oriented defaults. Map fusion uses simulator ground-truth poses as a shared reference; this does not establish localization robustness on hardware. Go2 assets are included. The AGIBOT X2 adapter requires external licensed assets and a walking controller. Learned locomotion, MPC, and WBC remain unimplemented controller placeholders.

**Stack:** Python, MuJoCo, Open3D, FastAPI, React, TypeScript, Three.js, and React Flow.

## Quick start

Requires [uv](https://docs.astral.sh/uv/) and Node.js 22.12+.

```bash
uv sync --python 3.12 --extra web --extra dev
cd frontend
npm ci
cd ..
uv run argus --scene flat --static
```

Open [localhost:8000](http://localhost:8000). The frontend builds at startup. Remove `--static` to enable motion, or use `--pick-spawn` to choose a scene and starting positions in the browser. On PowerShell, use `npm.cmd ci` if script policy blocks `npm`.

See the [usage guide](docs/usage.md) for office assets, optional detectors, CLI options, and development commands.

## Reproducible evaluation

```bash
uv run argus eval-locomotion --controller analytical_trot --scenario flat_ground --seed 101 --seed 202
```

Runs write `manifest.json`, `steps.jsonl`, `episodes.csv`, `summary.json`, and `comparison.md` under `outputs/locomotion-evals/`. The [benchmark guide](docs/locomotion-benchmark.md) covers scenarios, metrics, and comparison matrices.

## Future directions

These are research directions, not shipped features:

- **Experiment comparison:** Browse saved runs, replay failures, and compare results across scenarios and seeds.
- **Reusable robot data:** Record synchronized observations and actions, then add dataset import/export adapters.
- **Learned control:** Evaluate residual and direct policies against the analytical baseline before adding training workflows.
- **Robust coordination:** Study sensor noise, pose uncertainty, communication limits, and larger teams.
- **Persistent world models:** Connect the existing belief-graph prototype to live observations and test its value for task planning.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) and [design decisions](docs/adr/README.md)
- [Research methodology](docs/notes/research-method.md)
- [Systems design rationale](docs/notes/systems-design.md)
- [Origins and influences](docs/notes/origins.md)
- [Third-party licenses and assets](LICENSES.md)
