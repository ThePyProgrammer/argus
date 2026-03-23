"""Open3D pose-graph optimization merge strategy.

Builds a pose graph with odometry edges (within each robot) and
inter-robot loop closure edges (detected via ICP registration).
Runs Levenberg-Marquardt global optimization to produce globally
consistent poses, then re-projects frame clouds and union-merges voxels.

Loop closure fallback: when ICP fitness is below threshold, falls back
to known spawn transforms from MuJoCo config. Falls back to identity
only when spawn transforms are not available (graceful degradation).
"""

from __future__ import annotations

import logging
from itertools import combinations

import numpy as np
import open3d as o3d

from src.coordination.merge_protocol import MergeResult, RobotMapData
from src.coordination.merge_registry import merge_strategy

logger = logging.getLogger(__name__)


def _detect_loop_closure(
    cloud_a: o3d.geometry.PointCloud,
    cloud_b: o3d.geometry.PointCloud,
    max_corr_dist: float,
    fitness_threshold: float,
    min_points: int,
) -> tuple[bool, np.ndarray, float]:
    """Attempt ICP alignment between two point clouds.

    Returns:
        (success, transform_4x4, fitness_score). Guards against clouds
        with fewer than ``min_points`` points by returning failure.
    """
    if (
        len(cloud_a.points) < min_points
        or len(cloud_b.points) < min_points
    ):
        return False, np.eye(4), 0.0

    # Estimate normals for PointToPlane ICP
    for cloud in (cloud_a, cloud_b):
        if not cloud.has_normals():
            cloud.estimate_normals(
                o3d.geometry.KDTreeSearchParamHybrid(
                    radius=max_corr_dist * 2, max_nn=30
                )
            )

    result = o3d.pipelines.registration.registration_icp(
        cloud_a,
        cloud_b,
        max_corr_dist,
        np.eye(4),
        o3d.pipelines.registration.TransformationEstimationPointToPlane(),
    )
    success = result.fitness >= fitness_threshold
    return success, result.transformation, result.fitness


def _voxel_downsample_points(
    points: np.ndarray, resolution: float
) -> np.ndarray:
    """Grid-based voxel deduplication matching MapMerger.merge_voxels logic."""
    if points.size == 0:
        return np.empty((0, 3), dtype=np.float64)
    grid = np.round(points / resolution).astype(np.int64)
    _, idx = np.unique(grid, axis=0, return_index=True)
    return points[idx]


@merge_strategy(name="pgo_open3d", display="Open3D Pose-Graph")
class Open3DPGOStrategy:
    """Pose-graph optimization using Open3D's global optimizer.

    Builds odometry edges from consecutive poses within each robot and
    inter-robot loop closure edges from ICP registration. Falls back to
    spawn transforms when ICP fitness is below threshold.
    """

    CAPABILITIES = {
        "supports_loop_closure": True,
        "incremental": False,
        "supports_spawn_transforms": True,
    }

    PARAMETER_SCHEMA = {
        "type": "object",
        "properties": {
            "max_correspondence_distance": {
                "type": "number",
                "default": 0.15,
                "minimum": 0.01,
                "maximum": 1.0,
                "description": "Max ICP correspondence distance (m)",
                "live_tunable": False,
            },
            "edge_prune_threshold": {
                "type": "number",
                "default": 0.25,
                "minimum": 0.01,
                "maximum": 1.0,
                "description": "Edge prune threshold for PGO",
                "live_tunable": False,
            },
            "loop_closure_fitness_threshold": {
                "type": "number",
                "default": 0.3,
                "minimum": 0.05,
                "maximum": 0.9,
                "description": "Min ICP fitness for loop closure acceptance",
                "live_tunable": False,
            },
            "loop_closure_interval": {
                "type": "integer",
                "default": 5,
                "minimum": 1,
                "maximum": 50,
                "description": "Run loop closure every N merge cycles",
                "live_tunable": True,
            },
            "min_points_for_icp": {
                "type": "integer",
                "default": 50,
                "minimum": 10,
                "maximum": 1000,
                "description": "Min points in cloud for ICP registration",
                "live_tunable": False,
            },
        },
    }

    def __init__(
        self,
        max_correspondence_distance: float = 0.15,
        edge_prune_threshold: float = 0.25,
        loop_closure_fitness_threshold: float = 0.3,
        loop_closure_interval: int = 5,
        min_points_for_icp: int = 50,
        spawn_transforms: dict[str, np.ndarray] | None = None,
    ) -> None:
        self._max_corr_dist = max_correspondence_distance
        self._edge_prune_threshold = edge_prune_threshold
        self._loop_closure_fitness_threshold = loop_closure_fitness_threshold
        self._loop_closure_interval = loop_closure_interval
        self._min_points_for_icp = min_points_for_icp
        self._spawn_transforms = spawn_transforms or {}
        self._merge_count = 0
        self._last_merged_voxels: np.ndarray = np.empty((0, 3))
        self._last_merged_cloud: o3d.geometry.PointCloud = (
            o3d.geometry.PointCloud()
        )

    # ------------------------------------------------------------------
    # MergeProtocol interface
    # ------------------------------------------------------------------

    def merge(self, robot_data: dict[str, RobotMapData]) -> MergeResult:
        """Merge maps from multiple robots using pose-graph optimization."""
        robot_ids = sorted(robot_data.keys())

        # Trivial cases
        if len(robot_ids) == 0:
            return MergeResult(
                merged_voxels=np.empty((0, 3)),
                merged_cloud=o3d.geometry.PointCloud(),
                optimized_poses={},
                metrics={"strategy": "pgo_open3d"},
            )

        if len(robot_ids) == 1:
            rid = robot_ids[0]
            d = robot_data[rid]
            voxels = d.current_voxels.copy()
            cloud = o3d.geometry.PointCloud()
            if voxels.size > 0:
                cloud.points = o3d.utility.Vector3dVector(voxels)
            self._last_merged_voxels = voxels
            self._last_merged_cloud = cloud
            self._merge_count += 1
            return MergeResult(
                merged_voxels=voxels,
                merged_cloud=cloud,
                optimized_poses={rid: list(d.poses)},
                metrics={"strategy": "pgo_open3d"},
            )

        # Build pose graph
        pose_graph = o3d.pipelines.registration.PoseGraph()
        node_id = 0
        robot_node_ranges: dict[str, tuple[int, int]] = {}

        for rid in robot_ids:
            d = robot_data[rid]
            start = node_id
            for i, pose in enumerate(d.poses):
                pose_graph.nodes.append(
                    o3d.pipelines.registration.PoseGraphNode(pose)
                )
                # Odometry edge between consecutive poses
                if i > 0:
                    relative = np.linalg.inv(d.poses[i - 1]) @ pose
                    # Compute information matrix from frame clouds if available
                    if (
                        i < len(d.frame_clouds)
                        and i - 1 < len(d.frame_clouds)
                        and d.frame_clouds[i - 1].size > 0
                        and d.frame_clouds[i].size > 0
                    ):
                        src_cloud = o3d.geometry.PointCloud()
                        src_cloud.points = o3d.utility.Vector3dVector(
                            d.frame_clouds[i - 1]
                        )
                        tgt_cloud = o3d.geometry.PointCloud()
                        tgt_cloud.points = o3d.utility.Vector3dVector(
                            d.frame_clouds[i]
                        )
                        info = o3d.pipelines.registration.get_information_matrix_from_point_clouds(
                            src_cloud,
                            tgt_cloud,
                            self._max_corr_dist,
                            relative,
                        )
                    else:
                        info = np.eye(6)

                    pose_graph.edges.append(
                        o3d.pipelines.registration.PoseGraphEdge(
                            node_id - 1,
                            node_id,
                            relative,
                            info,
                            uncertain=False,
                        )
                    )
                node_id += 1
            robot_node_ranges[rid] = (start, node_id - 1)

        # Loop closure detection
        loop_closures_found = 0
        loop_closure_fallbacks = 0
        self._merge_count += 1

        if self._merge_count % self._loop_closure_interval == 0 or self._merge_count == 1:
            for rid_a, rid_b in combinations(robot_ids, 2):
                d_a = robot_data[rid_a]
                d_b = robot_data[rid_b]

                # Use latest frame cloud from each robot
                cloud_a_pts = d_a.frame_clouds[-1] if d_a.frame_clouds else np.empty((0, 3))
                cloud_b_pts = d_b.frame_clouds[-1] if d_b.frame_clouds else np.empty((0, 3))

                cloud_a = o3d.geometry.PointCloud()
                cloud_b = o3d.geometry.PointCloud()
                if cloud_a_pts.size > 0:
                    cloud_a.points = o3d.utility.Vector3dVector(cloud_a_pts)
                if cloud_b_pts.size > 0:
                    cloud_b.points = o3d.utility.Vector3dVector(cloud_b_pts)

                success, transform, fitness = _detect_loop_closure(
                    cloud_a,
                    cloud_b,
                    self._max_corr_dist,
                    self._loop_closure_fitness_threshold,
                    self._min_points_for_icp,
                )

                # Determine the edge endpoints: last node of each robot
                node_a = robot_node_ranges[rid_a][1]
                node_b = robot_node_ranges[rid_b][1]

                if success:
                    # ICP succeeded -- use ICP transform
                    info = np.eye(6)
                    if (
                        len(cloud_a.points) >= self._min_points_for_icp
                        and len(cloud_b.points) >= self._min_points_for_icp
                    ):
                        info = o3d.pipelines.registration.get_information_matrix_from_point_clouds(
                            cloud_a,
                            cloud_b,
                            self._max_corr_dist,
                            transform,
                        )
                    pose_graph.edges.append(
                        o3d.pipelines.registration.PoseGraphEdge(
                            node_a,
                            node_b,
                            transform,
                            info,
                            uncertain=True,
                        )
                    )
                    loop_closures_found += 1
                    logger.debug(
                        "Loop closure %s<->%s: fitness=%.3f",
                        rid_a, rid_b, fitness,
                    )
                else:
                    # ICP failed -- fall back to spawn transform or identity
                    fallback_transform = self._get_spawn_fallback_transform(
                        rid_a, rid_b
                    )
                    low_info = 0.1 * np.eye(6)
                    pose_graph.edges.append(
                        o3d.pipelines.registration.PoseGraphEdge(
                            node_a,
                            node_b,
                            fallback_transform,
                            low_info,
                            uncertain=True,
                        )
                    )
                    loop_closure_fallbacks += 1
                    logger.debug(
                        "Loop closure fallback %s<->%s (ICP fitness=%.3f)",
                        rid_a, rid_b, fitness,
                    )

        # Run global optimization
        option = o3d.pipelines.registration.GlobalOptimizationOption(
            max_correspondence_distance=self._max_corr_dist,
            edge_prune_threshold=self._edge_prune_threshold,
            reference_node=0,
        )
        o3d.pipelines.registration.global_optimization(
            pose_graph,
            o3d.pipelines.registration.GlobalOptimizationLevenbergMarquardt(),
            o3d.pipelines.registration.GlobalOptimizationConvergenceCriteria(),
            option,
        )

        # Extract optimized poses and re-project frame clouds
        optimized_poses: dict[str, list[np.ndarray]] = {}
        all_points: list[np.ndarray] = []

        for rid in robot_ids:
            start, end = robot_node_ranges[rid]
            d = robot_data[rid]
            opt_poses: list[np.ndarray] = []
            for i, node_idx in enumerate(range(start, end + 1)):
                opt_pose = pose_graph.nodes[node_idx].pose.copy()
                opt_poses.append(opt_pose)

                # Re-project frame cloud using optimized pose
                if i < len(d.frame_clouds) and d.frame_clouds[i].size > 0:
                    pts = d.frame_clouds[i]
                    transformed = (
                        opt_pose[:3, :3] @ pts.T
                    ).T + opt_pose[:3, 3]
                    all_points.append(transformed)

            optimized_poses[rid] = opt_poses

        # Union-merge into voxels
        if all_points:
            combined = np.vstack(all_points)
            merged_voxels = _voxel_downsample_points(combined, self._max_corr_dist)
        else:
            merged_voxels = np.empty((0, 3), dtype=np.float64)

        # Build merged cloud
        merged_cloud = o3d.geometry.PointCloud()
        if merged_voxels.size > 0:
            merged_cloud.points = o3d.utility.Vector3dVector(merged_voxels)

        self._last_merged_voxels = merged_voxels
        self._last_merged_cloud = merged_cloud

        return MergeResult(
            merged_voxels=merged_voxels,
            merged_cloud=merged_cloud,
            optimized_poses=optimized_poses,
            metrics={
                "strategy": "pgo_open3d",
                "graph_nodes": len(pose_graph.nodes),
                "graph_edges": len(pose_graph.edges),
                "loop_closures_found": loop_closures_found,
                "loop_closure_fallbacks": loop_closure_fallbacks,
            },
        )

    def reset(self) -> None:
        """Clear all accumulated merge state."""
        self._merge_count = 0
        self._last_merged_voxels = np.empty((0, 3))
        self._last_merged_cloud = o3d.geometry.PointCloud()

    @property
    def last_merged_voxels(self) -> np.ndarray:
        """Most recently merged voxel array."""
        return self._last_merged_voxels

    @property
    def last_merged_cloud(self) -> o3d.geometry.PointCloud:
        """Most recently merged point cloud."""
        return self._last_merged_cloud

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_spawn_fallback_transform(
        self, rid_a: str, rid_b: str
    ) -> np.ndarray:
        """Compute relative transform from spawn positions.

        Returns ``inv(spawn_a) @ spawn_b`` if both robot IDs exist in
        ``self._spawn_transforms``, otherwise returns ``np.eye(4)``.
        """
        if rid_a in self._spawn_transforms and rid_b in self._spawn_transforms:
            return (
                np.linalg.inv(self._spawn_transforms[rid_a])
                @ self._spawn_transforms[rid_b]
            )
        return np.eye(4)
