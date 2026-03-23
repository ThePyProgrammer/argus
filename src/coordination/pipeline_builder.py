"""Pipeline graph builder and node catalog.

Interprets a React Flow-style graph JSON into a PipelineConfig that
the coordinator can use to configure SLAM backends, merge strategies,
and filter chains. Validates DAG structure, required connections, and
node type availability via registries.
"""

import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any

from src.slam.registry import SLAMRegistry
from src.coordination.merge_registry import MergeRegistry

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """Interpreted pipeline configuration from a graph."""

    backend_name: str = "icp"
    backend_params: dict = field(default_factory=dict)
    merger_name: str = "icp_union"
    merger_params: dict = field(default_factory=dict)
    filter_chain: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Static node definitions
# ---------------------------------------------------------------------------

_STATIC_NODES: list[dict] = [
    {
        "type": "sensor_rgbd",
        "label": "RGB-D Sensor",
        "category": "sensor",
        "inputs": [],
        "outputs": [
            {"id": "image_out", "label": "Image", "dataType": "rgbd_frame"},
            {"id": "depth_out", "label": "Depth", "dataType": "depth_frame"},
        ],
        "parameterSchema": None,
        "defaultParams": {},
    },
    {
        "type": "sensor_imu",
        "label": "IMU Sensor",
        "category": "sensor",
        "inputs": [],
        "outputs": [
            {"id": "imu_out", "label": "IMU", "dataType": "imu_readings"},
        ],
        "parameterSchema": None,
        "defaultParams": {},
    },
    {
        "type": "filter_voxel_downsample",
        "label": "Voxel Downsample",
        "category": "filter",
        "inputs": [
            {"id": "cloud_in", "label": "Cloud", "dataType": "point_cloud", "required": True},
        ],
        "outputs": [
            {"id": "cloud_out", "label": "Cloud", "dataType": "point_cloud"},
        ],
        "parameterSchema": {
            "properties": {
                "voxel_size": {"type": "number", "default": 0.05},
            }
        },
        "defaultParams": {"voxel_size": 0.05},
    },
    {
        "type": "filter_noise_removal",
        "label": "Noise Removal",
        "category": "filter",
        "inputs": [
            {"id": "cloud_in", "label": "Cloud", "dataType": "point_cloud", "required": True},
        ],
        "outputs": [
            {"id": "cloud_out", "label": "Cloud", "dataType": "point_cloud"},
        ],
        "parameterSchema": {
            "properties": {
                "nb_neighbors": {"type": "integer", "default": 20},
                "std_ratio": {"type": "number", "default": 2.0},
            }
        },
        "defaultParams": {"nb_neighbors": 20, "std_ratio": 2.0},
    },
    {
        "type": "filter_coord_transform",
        "label": "Coordinate Transform",
        "category": "filter",
        "inputs": [
            {"id": "cloud_in", "label": "Cloud", "dataType": "point_cloud", "required": True},
        ],
        "outputs": [
            {"id": "cloud_out", "label": "Cloud", "dataType": "point_cloud"},
        ],
        "parameterSchema": {
            "properties": {
                "transform_matrix": {"type": "array", "default": None},
            }
        },
        "defaultParams": {},
    },
    {
        "type": "splitter",
        "label": "Splitter",
        "category": "utility",
        "inputs": [
            {"id": "in", "label": "Input", "dataType": "any", "required": True},
        ],
        "outputs": [
            {"id": "out_a", "label": "Output A", "dataType": "any"},
            {"id": "out_b", "label": "Output B", "dataType": "any"},
        ],
        "parameterSchema": None,
        "defaultParams": {},
    },
    {
        "type": "combiner",
        "label": "Combiner",
        "category": "utility",
        "inputs": [
            {"id": "in_a", "label": "Input A", "dataType": "any", "required": True},
            {"id": "in_b", "label": "Input B", "dataType": "any", "required": True},
        ],
        "outputs": [
            {"id": "out", "label": "Output", "dataType": "any"},
        ],
        "parameterSchema": None,
        "defaultParams": {},
    },
    {
        "type": "param_scalar",
        "label": "Scalar Parameter",
        "category": "parameter",
        "inputs": [],
        "outputs": [
            {"id": "value_out", "label": "Value", "dataType": "scalar"},
        ],
        "parameterSchema": {
            "properties": {
                "value": {"type": "number", "default": 0},
            }
        },
        "defaultParams": {"value": 0},
    },
    {
        "type": "viz_output",
        "label": "Visualization Output",
        "category": "output",
        "inputs": [
            {"id": "cloud_in", "label": "Cloud", "dataType": "point_cloud", "required": True},
        ],
        "outputs": [],
        "parameterSchema": None,
        "defaultParams": {},
    },
]

# Required input handles per node type prefix (for connection validation)
_REQUIRED_INPUTS: dict[str, list[str]] = {
    "slam_": ["image_in"],
    "merger_": ["cloud_in"],
}


class NodeCatalog:
    """Aggregates static node definitions with registry-discovered nodes."""

    @classmethod
    def get_catalog(cls) -> list[dict]:
        """Return unified catalog of all available node types.

        Combines static definitions with dynamically discovered SLAM
        backends and merge strategies from their respective registries.
        """
        catalog = list(_STATIC_NODES)

        # Add SLAM backends from registry
        for backend in SLAMRegistry.list_backends():
            catalog.append({
                "type": f"slam_{backend['name']}",
                "label": backend["display"],
                "category": "slam",
                "inputs": [
                    {"id": "image_in", "label": "Image", "dataType": "rgbd_frame", "required": True},
                    {"id": "imu_in", "label": "IMU", "dataType": "imu_readings", "required": False},
                ],
                "outputs": [
                    {"id": "pose_out", "label": "Pose", "dataType": "pose"},
                    {"id": "cloud_out", "label": "Cloud", "dataType": "point_cloud"},
                ],
                "parameterSchema": backend.get("parameter_schema", {}),
                "defaultParams": {},
                "registryName": backend["name"],
            })

        # Add merge strategies from registry
        for strategy in MergeRegistry.list_strategies():
            catalog.append({
                "type": f"merger_{strategy['name']}",
                "label": strategy["display"],
                "category": "merger",
                "inputs": [
                    {"id": "cloud_in", "label": "Cloud", "dataType": "point_cloud", "required": True},
                    {"id": "pose_in", "label": "Pose", "dataType": "pose", "required": False},
                ],
                "outputs": [
                    {"id": "merged_out", "label": "Merged", "dataType": "point_cloud"},
                ],
                "parameterSchema": strategy.get("parameter_schema", {}),
                "defaultParams": {},
                "registryName": strategy["name"],
            })

        return catalog


class PipelineBuilder:
    """Validates and interprets graph JSON into a PipelineConfig.

    Performs DAG validation (cycle detection), node type validation
    (against registries), required connection checks, parameter
    override resolution, and filter chain extraction.
    """

    def build(self, graph_json: dict) -> PipelineConfig:
        """Build a PipelineConfig from a React Flow-style graph.

        Args:
            graph_json: Dict with 'nodes' and 'edges' lists.

        Returns:
            PipelineConfig with backend, merger, and filter chain settings.

        Raises:
            ValueError: On cycles, unknown node types, or missing connections.
        """
        nodes = graph_json.get("nodes", [])
        edges = graph_json.get("edges", [])

        node_map: dict[str, dict] = {n["id"]: n for n in nodes}

        # 1. Validate DAG (topological sort via Kahn's algorithm)
        topo_order = self._topological_sort(nodes, edges)

        # 2. Validate node types and find SLAM/merger nodes
        known_types = self._get_known_types()

        slam_node = None
        merger_node = None

        for node in nodes:
            ntype = node["type"]

            # Check known static types
            if ntype in known_types:
                continue

            # Check SLAM backend prefix
            if ntype.startswith("slam_"):
                registry_name = ntype[len("slam_"):]
                backend_names = [b["name"] for b in SLAMRegistry.list_backends()]
                if registry_name not in backend_names:
                    raise ValueError(
                        f"Unknown SLAM backend: {registry_name}. "
                        f"Available: {backend_names}"
                    )
                continue

            # Check merger prefix
            if ntype.startswith("merger_"):
                registry_name = ntype[len("merger_"):]
                strategy_names = [s["name"] for s in MergeRegistry.list_strategies()]
                if registry_name not in strategy_names:
                    raise ValueError(
                        f"Unknown merge strategy: {registry_name}. "
                        f"Available: {strategy_names}"
                    )
                continue

            raise ValueError(
                f"Unknown node type: {ntype}"
            )

        # Find SLAM and merger nodes
        for node in nodes:
            if node["type"].startswith("slam_"):
                slam_node = node
            elif node["type"].startswith("merger_"):
                merger_node = node

        # 3. Validate required connections
        self._validate_required_connections(nodes, edges)

        # 4. Resolve parameter overrides
        self._resolve_param_overrides(node_map, edges)

        # 5. Extract config
        backend_name = "icp"
        backend_params: dict[str, Any] = {}
        if slam_node is not None:
            backend_name = slam_node["type"][len("slam_"):]
            backend_params = dict(slam_node.get("params", {}))

        merger_name = "icp_union"
        merger_params: dict[str, Any] = {}
        if merger_node is not None:
            merger_name = merger_node["type"][len("merger_"):]
            merger_params = dict(merger_node.get("params", {}))

        # 6. Build filter chain in topological order
        filter_chain = []
        for node_id in topo_order:
            node = node_map[node_id]
            if node["type"].startswith("filter_"):
                filter_chain.append({
                    "type": node["type"],
                    "params": dict(node.get("params", {})),
                })

        return PipelineConfig(
            backend_name=backend_name,
            backend_params=backend_params,
            merger_name=merger_name,
            merger_params=merger_params,
            filter_chain=filter_chain,
        )

    def _topological_sort(
        self, nodes: list[dict], edges: list[dict]
    ) -> list[str]:
        """Kahn's algorithm topological sort. Raises on cycle."""
        node_ids = {n["id"] for n in nodes}
        in_degree: dict[str, int] = {nid: 0 for nid in node_ids}
        adj: dict[str, list[str]] = defaultdict(list)

        for edge in edges:
            src = edge["source"]
            tgt = edge["target"]
            if src in node_ids and tgt in node_ids:
                adj[src].append(tgt)
                in_degree[tgt] += 1

        queue: deque[str] = deque()
        for nid, deg in in_degree.items():
            if deg == 0:
                queue.append(nid)

        order: list[str] = []
        while queue:
            nid = queue.popleft()
            order.append(nid)
            for neighbor in adj[nid]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(node_ids):
            remaining = node_ids - set(order)
            raise ValueError(
                f"Pipeline contains a cycle through nodes: {sorted(remaining)}"
            )

        return order

    def _get_known_types(self) -> set[str]:
        """Return set of all known static node types."""
        return {n["type"] for n in _STATIC_NODES}

    def _validate_required_connections(
        self, nodes: list[dict], edges: list[dict]
    ) -> None:
        """Check that required input handles are connected."""
        # Build set of (target_id, targetHandle) from edges
        connected_inputs: set[tuple[str, str]] = set()
        for edge in edges:
            connected_inputs.add((edge["target"], edge["targetHandle"]))

        for node in nodes:
            ntype = node["type"]
            for prefix, required_handles in _REQUIRED_INPUTS.items():
                if ntype.startswith(prefix):
                    for handle in required_handles:
                        if (node["id"], handle) not in connected_inputs:
                            raise ValueError(
                                f"Required input '{handle}' on node "
                                f"'{node['id']}' ({ntype}) is unconnected"
                            )

    def _resolve_param_overrides(
        self, node_map: dict[str, dict], edges: list[dict]
    ) -> None:
        """Apply param_scalar node values to connected target params."""
        for edge in edges:
            src_id = edge["source"]
            tgt_id = edge["target"]
            src_node = node_map.get(src_id)
            tgt_node = node_map.get(tgt_id)

            if src_node is None or tgt_node is None:
                continue

            if src_node["type"] == "param_scalar":
                value = src_node.get("params", {}).get("value")
                if value is not None:
                    param_key = edge["targetHandle"]
                    if "params" not in tgt_node:
                        tgt_node["params"] = {}
                    tgt_node["params"][param_key] = value
