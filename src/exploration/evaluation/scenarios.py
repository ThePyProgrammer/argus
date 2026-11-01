"""Static exploration fixtures and reproducible two-robot initial conditions.

The analytical mask here validates the axis-aligned benchmark fixtures only.
It is evaluation data, not a planning map or a general collision-map extractor.
Loading a fixture compiles its MJCF to check the independently authored geometry;
it does not create renderers, start physics, or import the application runtime.
"""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from numbers import Integral
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from src.metrics.exploration_reference import ReferenceGrid


SCENARIO_DIR = Path(__file__).resolve().parents[3] / "data" / "benchmarks" / "exploration"
SCENARIO_IDS = ("branching_corridor", "cluttered_room", "connected_rooms")
SCHEMA_VERSION = 1
REFERENCE_VERSION = "axis-aligned-square-clearance-v1"


@dataclass(frozen=True)
class StudyDefaults:
    """Development contract, to be frozen after the pilot, not runtime wiring."""

    platform: str = "go2"
    robot_count: int = 2
    sensor_width: int = 320
    sensor_height: int = 240
    sim_steps_per_frame: int = 5
    evaluation_resolution_m: float = 0.10
    map_resolution_m: float = 0.10
    clearance_half_extent_m: float = 0.40
    clearance_height_m: float = 0.60
    spawn_height_m: float = 0.30
    horizon_sim_seconds: float = 300.0
    coverage_threshold: float = 0.90
    slam_backend: str = "icp"
    merge_strategy: str = "icp_union"
    skill_learning_enabled: bool = False
    optional_inference_enabled: bool = False
    step_delay_seconds: float = 0.0


DEFAULTS = StudyDefaults()


@dataclass(frozen=True)
class Rectangle:
    """World XY bounds in meters."""

    x_min: float
    y_min: float
    x_max: float
    y_max: float

    def __post_init__(self) -> None:
        values = (self.x_min, self.y_min, self.x_max, self.y_max)
        if any(isinstance(v, bool) or not math.isfinite(v) for v in values):
            raise ValueError("Rectangle coordinates must be finite numbers")
        if self.x_min >= self.x_max or self.y_min >= self.y_max:
            raise ValueError("Rectangle must have positive width and height")


@dataclass(frozen=True)
class Obstacle:
    name: str
    bounds: Rectangle


@dataclass(frozen=True)
class SpawnPose:
    robot_id: str
    x: float
    y: float
    z: float
    yaw_rad: float


@dataclass(frozen=True)
class ScenarioSample:
    scenario_id: str
    scenario_sha256: str
    seed: int
    spawn_poses: tuple[SpawnPose, SpawnPose]
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> dict:
        """Return JSON-compatible resolved state, not just a seed label."""
        return asdict(self)


@dataclass(frozen=True)
class BenchmarkScenario:
    scenario_id: str
    description: str
    bounds: Rectangle
    obstacles: tuple[Obstacle, ...]
    component_anchor: tuple[float, float]
    spawn_pool: tuple[tuple[float, float], ...]
    headings_rad: tuple[float, ...]
    wall_height_m: float
    wall_thickness_m: float
    mjcf_xml: str
    scene_sha256: str
    metadata_sha256: str
    scenario_sha256: str

    def is_clear(self, x: float, y: float) -> bool:
        """Conservative square footprint clearance, including the outer walls."""
        if not math.isfinite(x) or not math.isfinite(y):
            return False
        r, b = DEFAULTS.clearance_half_extent_m, self.bounds
        if not (b.x_min + r < x < b.x_max - r and b.y_min + r < y < b.y_max - r):
            return False
        return not any(
            o.bounds.x_min - r <= x <= o.bounds.x_max + r
            and o.bounds.y_min - r <= y <= o.bounds.y_max + r
            for o in self.obstacles
        )

    def reference_mask(self, resolution_m: float = DEFAULTS.evaluation_resolution_m) -> np.ndarray:
        """Cell-center mask of the fixed component containing the declared anchor.

        Rows increase with world Y, columns with world X. Clearance uses a square
        envelope, deliberately more conservative than circular corner clearance.
        This function never takes robot observations or episode outcomes.
        """
        width, height = _grid_shape(self.bounds, resolution_m)
        b, r = self.bounds, DEFAULTS.clearance_half_extent_m
        xs = b.x_min + (np.arange(width) + 0.5) * resolution_m
        ys = b.y_min + (np.arange(height) + 0.5) * resolution_m
        xx, yy = np.meshgrid(xs, ys)
        mask = ((xx > b.x_min + r) & (xx < b.x_max - r)
                & (yy > b.y_min + r) & (yy < b.y_max - r))
        for obstacle in self.obstacles:
            o = obstacle.bounds
            mask &= ~((xx >= o.x_min - r) & (xx <= o.x_max + r)
                      & (yy >= o.y_min - r) & (yy <= o.y_max + r))
        anchor = self._cell(*self.component_anchor, resolution_m)
        if not self.is_clear(*self.component_anchor) or not mask[anchor]:
            raise ValueError("Reference component anchor is not clear")
        component = np.zeros_like(mask)
        component[anchor] = True
        queue = deque([anchor])
        while queue:
            row, col = queue.popleft()
            for nr, nc in ((row - 1, col), (row + 1, col), (row, col - 1), (row, col + 1)):
                if 0 <= nr < height and 0 <= nc < width and mask[nr, nc] and not component[nr, nc]:
                    component[nr, nc] = True
                    queue.append((nr, nc))
        component.setflags(write=False)
        return component

    def _cell(self, x: float, y: float, resolution_m: float) -> tuple[int, int]:
        b = self.bounds
        if not (b.x_min <= x < b.x_max and b.y_min <= y < b.y_max):
            raise ValueError("Point is outside the benchmark bounds")
        return (math.floor((y - b.y_min) / resolution_m), math.floor((x - b.x_min) / resolution_m))

    def reference_metadata(self, resolution_m: float = DEFAULTS.evaluation_resolution_m) -> dict:
        """Describe the immutable denominator independently of a sampled spawn."""
        mask = self.reference_mask(resolution_m)
        return {
            "reference_version": REFERENCE_VERSION,
            "scenario_sha256": self.scenario_sha256,
            "mask_sha256": hashlib.sha256(mask.tobytes(order="C")).hexdigest(),
            "resolution_m": resolution_m,
            "origin_xy": [self.bounds.x_min, self.bounds.y_min],
            "shape_rows_columns": list(mask.shape),
            "row_direction": "positive_world_y",
            "clearance_half_extent_m": DEFAULTS.clearance_half_extent_m,
            "clearance_height_m": DEFAULTS.clearance_height_m,
            "component_anchor_xy": list(self.component_anchor),
            "cell_count": int(mask.sum()),
            "area_m2": float(mask.sum() * resolution_m**2),
        }

    def compiled_reference(self, resolution_m: float = DEFAULTS.evaluation_resolution_m) -> ReferenceGrid:
        """Build the evaluation grid independently from compiled collision shapes.

        The analytical mask remains a separate validation oracle. This method is
        for evaluation tooling and is not part of the robot's planning inputs.
        """
        import mujoco
        from src.metrics.exploration_reference import ReferenceConfig, build_reference_grid

        b = self.bounds
        config = ReferenceConfig(
            bounds=(b.x_min, b.y_min, b.x_max, b.y_max),
            component_anchor=self.component_anchor,
            resolution_m=resolution_m,
            clearance_half_extent_m=DEFAULTS.clearance_half_extent_m,
            clearance_height_m=DEFAULTS.clearance_height_m,
        )
        return build_reference_grid(mujoco.MjModel.from_xml_string(self.mjcf_xml), config)

    def validate_spawn_pair(self, poses: tuple[SpawnPose, SpawnPose]) -> None:
        if len(poses) != 2 or tuple(p.robot_id for p in poses) != ("robot_a", "robot_b"):
            raise ValueError("Exactly robot_a and robot_b are required in that order")
        mask = self.reference_mask()
        for pose in poses:
            if not all(math.isfinite(v) for v in (pose.x, pose.y, pose.z, pose.yaw_rad)):
                raise ValueError("Spawn pose must be finite")
            if pose.z != DEFAULTS.spawn_height_m:
                raise ValueError("Spawn height must match the Go2 benchmark contract")
            if not self.is_clear(pose.x, pose.y) or not mask[self._cell(pose.x, pose.y, DEFAULTS.evaluation_resolution_m)]:
                raise ValueError("Spawn must be clear and in the fixed reference component")
        a, b = poses
        diameter = 2 * DEFAULTS.clearance_half_extent_m
        if abs(a.x - b.x) <= diameter and abs(a.y - b.y) <= diameter:
            raise ValueError("Spawn clearance envelopes overlap")

    def sample(self, seed: int) -> ScenarioSample:
        if isinstance(seed, bool) or not isinstance(seed, Integral) or not 0 <= seed < 2**32:
            raise ValueError("Seed must be an integer in [0, 2**32)")
        seed = int(seed)
        diameter = 2 * DEFAULTS.clearance_half_extent_m
        pairs = [(a, b) for a in self.spawn_pool for b in self.spawn_pool
                 if abs(a[0] - b[0]) > diameter or abs(a[1] - b[1]) > diameter]
        if not pairs:
            raise ValueError("No non-overlapping spawn pairs")
        # Named stream positions are stable: 0 for locations, 1 for headings.
        locations = np.random.default_rng(np.random.SeedSequence([seed, 0]))
        headings = np.random.default_rng(np.random.SeedSequence([seed, 1]))
        a, b = pairs[int(locations.integers(len(pairs)))]
        poses = tuple(
            SpawnPose(rid, *xy, DEFAULTS.spawn_height_m, float(headings.choice(self.headings_rad)))
            for rid, xy in zip(("robot_a", "robot_b"), (a, b))
        )
        self.validate_spawn_pair(poses)
        return ScenarioSample(self.scenario_id, self.scenario_sha256, seed, poses)


def list_scenarios() -> tuple[str, ...]:
    return SCENARIO_IDS


def load_scenario(scenario_id: str, *, scenario_dir: Path = SCENARIO_DIR) -> BenchmarkScenario:
    """Load and validate a versioned fixture before constructing an episode."""
    if scenario_id not in SCENARIO_IDS:
        raise ValueError(f"Unknown exploration scenario {scenario_id!r}. Available: {SCENARIO_IDS}")
    metadata_bytes = (scenario_dir / f"{scenario_id}.json").read_bytes()
    xml_bytes = (scenario_dir / f"{scenario_id}.xml").read_bytes()
    payload = json.loads(metadata_bytes)
    expected_keys = {"schema_version", "scenario_id", "description", "source", "license",
                     "bounds", "obstacles", "component_anchor", "spawn_pool", "headings_deg",
                     "wall_height_m", "wall_thickness_m"}
    if not isinstance(payload, dict) or set(payload) != expected_keys:
        raise ValueError("Scenario metadata keys do not match schema v1")
    if type(payload["schema_version"]) is not int or payload["schema_version"] != SCHEMA_VERSION:
        raise ValueError("Unsupported scenario schema version")
    if payload["scenario_id"] != scenario_id:
        raise ValueError("Scenario ID does not match its filename")
    bounds = Rectangle(*_numbers(payload["bounds"], 4))
    obstacles = []
    for item in payload["obstacles"]:
        if not isinstance(item, dict) or set(item) != {"name", "bounds"}:
            raise ValueError("Obstacle must contain name and bounds")
        if not isinstance(item["name"], str) or not item["name"].startswith("obstacle_"):
            raise ValueError("Obstacle names must start with obstacle_")
        obstacle = Obstacle(item["name"], Rectangle(*_numbers(item["bounds"], 4)))
        o = obstacle.bounds
        if not (bounds.x_min <= o.x_min < o.x_max <= bounds.x_max
                and bounds.y_min <= o.y_min < o.y_max <= bounds.y_max):
            raise ValueError("Obstacle lies outside the benchmark bounds")
        obstacles.append(obstacle)
    if len({o.name for o in obstacles}) != len(obstacles):
        raise ValueError("Duplicate obstacle names")
    spawn_pool = tuple(_numbers(p, 2) for p in payload["spawn_pool"])
    if len(spawn_pool) < 2 or len(set(spawn_pool)) != len(spawn_pool):
        raise ValueError("Spawn pool needs at least two unique points")
    headings = tuple(math.radians(v) for v in _numbers(payload["headings_deg"]))
    if not headings or len(set(headings)) != len(headings):
        raise ValueError("Heading samples must be nonempty and unique")
    wall_height, wall_thickness = _numbers([payload["wall_height_m"], payload["wall_thickness_m"]], 2)
    if wall_height < DEFAULTS.clearance_height_m or wall_thickness <= 0:
        raise ValueError("Walls must enclose the full clearance envelope")
    for name in ("description", "source", "license"):
        if not isinstance(payload[name], str) or not payload[name].strip():
            raise ValueError(f"Scenario {name} must be a nonempty string")
    scenario = BenchmarkScenario(
        scenario_id, payload["description"], bounds, tuple(obstacles),
        _numbers(payload["component_anchor"], 2), spawn_pool, headings,
        wall_height, wall_thickness, xml_bytes.decode("utf-8"),
        hashlib.sha256(xml_bytes).hexdigest(), hashlib.sha256(metadata_bytes).hexdigest(),
        hashlib.sha256(metadata_bytes + b"\0" + xml_bytes).hexdigest(),
    )
    mask = scenario.reference_mask()
    for x, y in spawn_pool:
        if not scenario.is_clear(x, y) or not mask[scenario._cell(x, y, DEFAULTS.evaluation_resolution_m)]:
            raise ValueError("Every spawn pool point must lie in the clear reference component")
    _validate_mjcf(scenario)
    scenario.sample(0)  # Also reject a pool with no feasible pair.
    return scenario


def _numbers(values: list, length: int | None = None) -> tuple[float, ...]:
    if not isinstance(values, list) or (length is not None and len(values) != length):
        raise ValueError("Expected a numeric list of the declared length")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
        raise ValueError("Coordinates and dimensions must be finite numbers")
    return tuple(float(v) for v in values)


def _grid_shape(bounds: Rectangle, resolution_m: float) -> tuple[int, int]:
    if isinstance(resolution_m, bool) or not math.isfinite(resolution_m) or resolution_m <= 0:
        raise ValueError("Resolution must be finite and positive")
    shape = ((bounds.x_max - bounds.x_min) / resolution_m,
             (bounds.y_max - bounds.y_min) / resolution_m)
    if any(not math.isfinite(n) for n in shape):
        raise ValueError("Reference grid dimensions must be finite")
    if any(not math.isclose(n, round(n), abs_tol=1e-8, rel_tol=0) for n in shape):
        raise ValueError("Grid resolution must divide the scene bounds exactly")
    width, height = map(round, shape)
    if width < 1 or height < 1 or width * height > 1_000_000:
        raise ValueError("Reference grid must contain 1 to 1,000,000 cells")
    return width, height


def _validate_mjcf(scenario: BenchmarkScenario) -> None:
    """Check compiled collision boxes against the analytical fixture metadata."""
    import mujoco

    model = mujoco.MjModel.from_xml_string(scenario.mjcf_xml)
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    if model.nq or model.nv or model.nbody != 1:
        raise ValueError("Benchmark MJCF must contain static world geometry only")
    b, t = scenario.bounds, scenario.wall_thickness_m
    h = scenario.wall_height_m
    boxes = {
        "floor": (Rectangle(b.x_min - t, b.y_min - t, b.x_max + t, b.y_max + t), -0.10, 0.0),
        "boundary_west": (Rectangle(b.x_min - t, b.y_min, b.x_min, b.y_max), 0.0, h),
        "boundary_east": (Rectangle(b.x_max, b.y_min, b.x_max + t, b.y_max), 0.0, h),
        "boundary_south": (Rectangle(b.x_min - t, b.y_min - t, b.x_max + t, b.y_min), 0.0, h),
        "boundary_north": (Rectangle(b.x_min - t, b.y_max, b.x_max + t, b.y_max + t), 0.0, h),
    }
    boxes.update({o.name: (o.bounds, 0.0, h) for o in scenario.obstacles})
    names = {mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, i) for i in range(model.ngeom)}
    if names != set(boxes) or model.ngeom != len(boxes):
        raise ValueError("Compiled scene geometry does not match the metadata")
    for name, (rect, z_min, z_max) in boxes.items():
        i = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, name)
        center = [(rect.x_min + rect.x_max) / 2, (rect.y_min + rect.y_max) / 2, (z_min + z_max) / 2]
        size = [(rect.x_max - rect.x_min) / 2, (rect.y_max - rect.y_min) / 2, (z_max - z_min) / 2]
        if (model.geom_type[i] != mujoco.mjtGeom.mjGEOM_BOX
                or model.geom_contype[i] != 1 or model.geom_conaffinity[i] != 1
                or not np.allclose(data.geom_xmat[i], np.eye(3).ravel(), atol=1e-10, rtol=0)
                or not np.allclose(data.geom_xpos[i], center, atol=1e-10, rtol=0)
                or not np.allclose(model.geom_size[i], size, atol=1e-10, rtol=0)):
            raise ValueError(f"Compiled collision geometry disagrees with metadata: {name}")
