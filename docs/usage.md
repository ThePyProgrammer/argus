# Usage and development

For a minimal installation, start with the [README](../README.md#quick-start). This guide collects operational details previously kept there.

## Scenes and spawning

```bash
uv run argus --scene office --static
uv run argus --pick-spawn
```

The spawn picker offers the original office, an open floor, and nine bundled environments: chemistry lab, chess room, coffee shop, gym, living room, modern office, playground, restaurant, and workbench. Select a scene, place each robot on clear floor, and start the simulation. **Use default positions** skips manual placement. **Restart** opens the same picker to change scenes or placements.

The browser environment mesh shows the authored initial layout. Loose props can move in physics; RGB feeds show their live positions. The bundled scenes require MuJoCo 3.6+, included in the Python dependencies. See [scene sources and compatibility notes](../data/scene_library/prompt/SOURCE.md).

If the original office's OBJ assets are missing or remain Git LFS pointers, Argus can recover meshes from `frontend/public/scene.glb`. Missing textures use material colors. Install Git LFS and run `git lfs pull` for the original assets. Objects missing from the LFS server require an original clone or backup. The flat scene contains only a checkerboard floor.

## Optional perception

Install the YOLO dependencies before running detection:

```bash
uv sync --python 3.12 --extra web --extra detection --extra dev
uv run --extra web --extra detection argus --scene office --static
```

BoxeR uses a separate environment with OWLv2 proposals and native 3D boxes:

```bash
uv run python scripts/setup_boxer_subprocess.py
uv run --extra web argus --scene office --static --detector boxer --num-robots 1
```

Setup downloads approximately 1.3 GB of checkpoints. CPU inference is slower than YOLO, so start with one robot. BoxeR also appears in the dashboard's detector selector after setup.

Optional Moondream2 scene descriptions require the model dependencies and system `libvips`. Descriptions are disabled by default. Model availability and external SLAM dependencies vary by backend.

## Common CLI options

Use `uv run argus --help` for the complete reference.

| Flag | Default | Purpose |
| --- | --- | --- |
| `--control` | `web` | `web`, `multi`, `explore`, `teleop`, `waypoint`, or `random`. |
| `--scene` | `flat` | Select a scene from the bundled library. |
| `--pick-spawn` | off | Choose scene and spawn positions in the browser. |
| `--port` | `8000` | Dashboard port. |
| `--num-robots` | `2` | Robot count in multi-robot modes. |
| `--static` | off | Keep robots stationary while sensing continues. |
| `--multi-max-steps` | `0` | Step limit; zero runs until stopped. |
| `--multi-boot-steps` | `200` | Initial physics settling steps. |
| `--octomap-resolution` | `0.1` | Voxel resolution in meters. |
| `--platform` | `go2` | `go2` or `agibot_x2`. |
| `--x2-model-dir` | `models/agibot_x2` | External X2 assets. |
| `--x2-controller` | unset | External X2 controller path. |

Go2 assets are committed. X2 requires separately supplied licensed assets and a suitable controller for walking. Its default controller behavior without a policy is to hold joint positions.

## Agent access

Argus exposes a JSON-RPC MCP endpoint at `/mcp`. For Claude Code:

```bash
claude mcp add --transport http argus http://localhost:8000/mcp
```

Tools include `get_status`, `get_detections`, `get_scene_description`, `send_command`, and `get_coverage`. They expose simulation state and commands such as pause, resume, stop, and speed changes. Scene descriptions require the optional VLM.

## Development

Start the backend from the repository root:

```bash
uv run argus --scene office --port 8000
```

In another terminal, run the frontend with hot reload:

```bash
cd frontend
npm run dev
```

The Vite proxy defaults to backend port 8000. Set `VITE_BACKEND_PORT` in the frontend terminal when using a different port.

Run checks from the repository root:

```bash
uv run python -m pytest tests/ -x --timeout=30
cd frontend
npm test
npm run build
```

Some integration tests require optional models or assets. To regenerate the original office GLB, run `uv run python scripts/convert_scene_glb.py`; output goes to `frontend/public/scene.glb`.

## Code map

| Path | Responsibility |
| --- | --- |
| `src/bridge/` | Simulation, sensors, scenes, and platform adapters. |
| `src/slam/`, `src/perception/`, `src/tracking/` | Mapping, detection, lifting, and tracking. |
| `src/exploration/`, `src/coordination/` | Navigation and multi-robot orchestration. |
| `src/locomotion/` | Controllers, environments, metrics, and evaluation. |
| `src/representation/` | Experimental belief graph and query API. |
| `backend/web/`, `frontend/src/` | API, streaming, dashboard, and pipeline editor. |
| `tests/` | Unit, integration, smoke, and contract checks. |

See [architecture](ARCHITECTURE.md) for module boundaries and [locomotion benchmarks](locomotion-benchmark.md) for evaluation workflows.
