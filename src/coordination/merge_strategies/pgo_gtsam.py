"""GTSAM iSAM2 incremental pose-graph optimization merge strategy.

Uses GTSAM's incremental Bayes tree (iSAM2) for efficient pose-graph
optimization that reuses previous solutions. GTSAM is an optional
dependency -- the strategy reports unavailable with install hint when
gtsam is not installed.

Loop closure fallback: same pattern as Open3D PGO -- falls back to
spawn transforms from MuJoCo config when ICP fitness is below threshold.
"""

from __future__ import annotations

import logging
from itertools import combinations

import numpy as np
import open3d as o3d

from src.coordination.merge_protocol import MergeResult, RobotMapData
from src.coordination.merge_registry import merge_strategy
from src.coordination.merge_strategies.pgo_open3d import (
    _detect_loop_closure,
    _voxel_downsample_points,
)

logger = logging.getLogger(__name__)

try:
    import gtsam

    GTSAM_AVAILABLE = True
except ImportError:
    GTSAM_AVAILABLE = False


@merge_strategy(name="pgo_gtsam", display="GTSAM iSAM2 PGO")
class GTSAMPGOStrategy:
    """Incremental pose-graph optimization using GTSAM iSAM2.

    Builds BetweenFactorPose3 factors for odometry and loop closure
    constraints, then runs incremental Bayes tree updates. GTSAM is
    an optional dependency.
    """

    AVAILABLE = GTSAM_AVAILABLE
    INSTALL_HINT = "pip install gtsam"

    CAPABILITIES = {
        "supports_loop_closure": True,
        "incremental": True,
        "supports_spawn_transforms": True,
    }

    PARAMETER_SCHEMA = {
        "type": "object",
        "properties": {
            "prior_rot_sigma": {
                "type": "number",
                "default": 0.01,
                "description": "Prior rotation sigma (rad)",
                "live_tunable": False,
            },
            "prior_trans_sigma": {
                "type": "number",
                "default": 0.05,
                "description": "Prior translation sigma (m)",
                "live_tunable": False,
            },
            "odom_rot_sigma": {
                "type": "number",
                "default": 0.05,
                "description": "Odometry rotation sigma (rad)",
                "live_tunable": False,
            },
            "odom_trans_sigma": {
                "type": "number",
                "default": 0.1,
                "description": "Odometry translation sigma (m)",
                "live_tunable": False,
            },
            "loop_rot_sigma": {
                "type": "number",
                "default": 0.1,
                "description": "Loop closure rotation sigma (rad)",
                "live_tunable": False,
            },
            "loop_trans_sigma": {
                "type": "number",
                "default": 0.2,
                "description": "Loop closure translation sigma (m)",
                "live_tunable": False,
            },
            "loop_closure_fitness_threshold": {
                "type": "number",
                "default": 0.3,
                "live_tunable": False,
            },
            "loop_closure_interval": {
                "type": "integer",
                "default": 5,
                "live_tunable": False,
            },
            "min_points_for_icp": {
                "type": "integer",
                "default": 50,
                "live_tunable": False,
            },
        },
    }

    def __init__(
        self,
        prior_rot_sigma: float = 0.01,
        prior_trans_sigma: float = 0.05,
        odom_rot_sigma: float = 0.05,
        odom_trans_sigma: float = 0.1,
        loop_rot_sigma: float = 0.1,
        loop_trans_sigma: float = 0.2,
        loop_closure_fitness_threshold: float = 0.3,
        loop_closure_interval: int = 5,
        min_points_for_icp: int = 50,
        spawn_transforms: dict[str, np.ndarray] | None = None,
    ) -> None:
        if not GTSAM_AVAILABLE:
            raise ImportError(
                "gtsam not installed. Install with: pip install gtsam"
            )

        self._spawn_transforms = spawn_transforms or {}
        self._loop_closure_fitness_threshold = loop_closure_fitness_threshold
        self._loop_closure_interval = loop_closure_interval
        self._min_points_for_icp = min_points_for_icp
        self._max_corr_dist = 0.15  # for ICP detection

        # Noise models (6D: rx, ry, rz, tx, ty, tz)
        self._prior_noise = gtsam.noiseModel.Diagonal.Sigmas(
            np.array([prior_rot_sigma] * 3 + [prior_trans_sigma] * 3)
        )
        self._odom_noise = gtsam.noiseModel.Diagonal.Sigmas(
            np.array([odom_rot_sigma] * 3 + [odom_trans_sigma] * 3)
        )
        self._loop_noise = gtsam.noiseModel.Diagonal.Sigmas(
            np.array([loop_rot_sigma] * 3 + [loop_trans_sigma] * 3)
        )
        # Inflated noise for spawn-transform fallbacks (3x loop sigma)
        self._fallback_noise = gtsam.noiseModel.Diagonal.Sigmas(
            np.array([loop_rot_sigma * 3] * 3 + [loop_trans_sigma * 3] * 3)
        )

        self._isam2_params = gtsam.ISAM2Params()
        self._isam2_params.setRelinearizeThreshold(0.1)
        self._isam2_params.relinearizeSkip = 1

        self._isam: gtsam.ISAM2 = gtsam.ISAM2(self._isam2_params)
        self._update_count = 0
        self._merge_count = 0
        self._robot_key_ranges: dict[str, tuple[int, int]] = {}
        self._last_merged_voxels: np.ndarray = np.empty((0, 3))
        self._last_merged_cloud: o3d.geometry.PointCloud = (
            o3d.geometry.PointCloud()
        )

    # ------------------------------------------------------------------
    # MergeProtocol interface
    # ------------------------------------------------------------------

    def merge(self, robot_data: dict[str, RobotMapData]) -> MergeResult:
        """Merge maps using incremental iSAM2 optimization."""
        robot_ids = sorted(robot_data.keys())

        # Trivial cases
        if len(robot_ids) == 0:
            self._update_count += 1
            return MergeResult(
                merged_voxels=np.empty((0, 3)),
                merged_cloud=o3d.geometry.PointCloud(),
                optimized_poses={},
                metrics={
                    "strategy": "pgo_gtsam",
                    "isam2_updates": self._update_count,
                },
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
            self._update_count += 1
            return MergeResult(
                merged_voxels=voxels,
                merged_cloud=cloud,
                optimized_poses={rid: list(d.poses)},
                metrics={
                    "strategy": "pgo_gtsam",
                    "isam2_updates": self._update_count,
                },
            )

        # Build incremental factor graph
        graph = gtsam.NonlinearFactorGraph()
        initial = gtsam.Values()

        # Assign keys per robot using gtsam.symbol
        robot_keys: dict[str, list[int]] = {}
        first_key_added = False

        for rid in robot_ids:
            d = robot_data[rid]
            # Use last character of robot_id for symbol char
            sym_char = ord(rid[-1])
            keys: list[int] = []

            for i, pose in enumerate(d.poses):
                key = gtsam.symbol(sym_char, i)
                keys.append(key)
                pose3 = gtsam.Pose3(pose)

                # Add initial value
                if not initial.exists(key):
                    initial.insert(key, pose3)

                # Prior on first node of first robot
                if not first_key_added:
                    graph.push_back(
                        gtsam.PriorFactorPose3(key, pose3, self._prior_noise)
                    )
                    first_key_added = True

                # Odometry edge
                if i > 0:
                    prev_key = keys[i - 1]
                    relative = np.linalg.inv(d.poses[i - 1]) @ pose
                    rel_pose3 = gtsam.Pose3(relative)
                    graph.push_back(
                        gtsam.BetweenFactorPose3(
                            prev_key, key, rel_pose3, self._odom_noise
                        )
                    )

            robot_keys[rid] = keys

        # Loop closure detection
        loop_closures_found = 0
        loop_closure_fallbacks = 0
        self._merge_count += 1

        if (
            self._merge_count % self._loop_closure_interval == 0
            or self._merge_count == 1
        ):
            for rid_a, rid_b in combinations(robot_ids, 2):
                d_a = robot_data[rid_a]
                d_b = robot_data[rid_b]

                cloud_a_pts = (
                    d_a.frame_clouds[-1]
                    if d_a.frame_clouds
                    else np.empty((0, 3))
                )
                cloud_b_pts = (
                    d_b.frame_clouds[-1]
                    if d_b.frame_clouds
                    else np.empty((0, 3))
                )

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

                key_a = robot_keys[rid_a][-1]
                key_b = robot_keys[rid_b][-1]

                if success:
                    rel_pose3 = gtsam.Pose3(transform)
                    graph.push_back(
                        gtsam.BetweenFactorPose3(
                            key_a, key_b, rel_pose3, self._loop_noise
                        )
                    )
                    loop_closures_found += 1
                else:
                    fallback = self._get_spawn_fallback_transform(
                        rid_a, rid_b
                    )
                    rel_pose3 = gtsam.Pose3(fallback)
                    graph.push_back(
                        gtsam.BetweenFactorPose3(
                            key_a, key_b, rel_pose3, self._fallback_noise
                        )
                    )
                    loop_closure_fallbacks += 1

        # Incremental update
        self._isam.update(graph, initial)
        self._update_count += 1
        result = self._isam.calculateEstimate()

        # Extract optimized poses and re-project
        optimized_poses: dict[str, list[np.ndarray]] = {}
        all_points: list[np.ndarray] = []

        for rid in robot_ids:
            d = robot_data[rid]
            opt_poses: list[np.ndarray] = []
            for i, key in enumerate(robot_keys[rid]):
                opt_pose = result.atPose3(key).matrix()
                opt_poses.append(opt_pose)

                if i < len(d.frame_clouds) and d.frame_clouds[i].size > 0:
                    pts = d.frame_clouds[i]
                    transformed = (
                        opt_pose[:3, :3] @ pts.T
                    ).T + opt_pose[:3, 3]
                    all_points.append(transformed)

            optimized_poses[rid] = opt_poses

        # Union-merge voxels
        if all_points:
            combined = np.vstack(all_points)
            merged_voxels = _voxel_downsample_points(combined, self._max_corr_dist)
        else:
            merged_voxels = np.empty((0, 3), dtype=np.float64)

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
                "strategy": "pgo_gtsam",
                "isam2_updates": self._update_count,
                "loop_closures_found": loop_closures_found,
                "loop_closure_fallbacks": loop_closure_fallbacks,
            },
        )

    def reset(self) -> None:
        """Clear iSAM2 state and re-create the optimizer."""
        self._isam = gtsam.ISAM2(self._isam2_params)
        self._update_count = 0
        self._merge_count = 0
        self._robot_key_ranges = {}
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
