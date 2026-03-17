#!/usr/bin/env python3
"""Main entry point: MuJoCo bridge -> SLAM -> OctoMap -> Rerun visualization.

Wires all Phase 1 modules into a single run loop:
  1. MuJoCoBridge produces SensorFrames each step (Go2 in MuJoCo)
  2. SLAMPipeline estimates poses via ICP odometry
  3. OctoMapBuilder accumulates occupancy grid
  4. GroundTruthCollector records GT for drift comparison
  5. RerunVisualizer streams everything to the Rerun viewer
  6. At shutdown, compute_drift_metrics prints ATE/RPE

Control modes:
  --control teleop    : WASD keyboard control (default, requires pynput)
  --control waypoint  : Scripted waypoint following
  --control random    : Random exploration
"""

import argparse
import math
import sys
import time

import numpy as np

from src.bridge.env_config import MuJoCoEnvConfig
from src.bridge.sensor_types import CameraIntrinsics
from src.bridge.sim_bridge import MuJoCoBridge
from src.control.random_walk import RandomWalkController
from src.control.waypoint_runner import WaypointRunner
from src.metrics.drift_metrics import compute_drift_metrics
from src.metrics.ground_truth import GroundTruthCollector
from src.slam.octomap_builder import OctoMapBuilder
from src.slam.slam_pipeline import SLAMPipeline
from src.viz.rerun_viz import RerunVisualizer


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Single-robot SLAM in MuJoCo")
    parser.add_argument(
        "--control",
        choices=["teleop", "waypoint", "random"],
        default="teleop",
        help="Control mode (default: teleop)",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=1000,
        help="Maximum simulation steps (default: 1000)",
    )
    parser.add_argument(
        "--octomap-resolution",
        type=float,
        default=0.1,
        help="OctoMap voxel resolution in meters (default: 0.1)",
    )
    parser.add_argument(
        "--octomap-interval",
        type=int,
        default=5,
        help="Insert into OctoMap every N frames (default: 5)",
    )
    parser.add_argument(
        "--no-viz",
        action="store_true",
        help="Disable Rerun visualization",
    )
    return parser.parse_args()


def create_controller(mode: str):
    """Create the appropriate controller for the given mode.

    Args:
        mode: One of 'teleop', 'waypoint', 'random'.

    Returns:
        A controller instance with a ``get_velocity(...)`` method.
    """
    if mode == "teleop":
        from src.control.teleop import TeleopController

        return TeleopController()
    elif mode == "waypoint":
        return WaypointRunner(
            waypoints=[
                np.array([5.0, 0.0, 0.0]),
                np.array([5.0, 5.0, 0.0]),
                np.array([0.0, 5.0, 0.0]),
                np.array([0.0, 0.0, 0.0]),
            ]
        )
    elif mode == "random":
        return RandomWalkController(seed=42)
    else:
        raise ValueError(f"Unknown control mode: {mode}")


def main():
    """Run the single-robot SLAM loop."""
    args = parse_args()

    # ------------------------------------------------------------------
    # Initialize components
    # ------------------------------------------------------------------
    config = MuJoCoEnvConfig()
    bridge = MuJoCoBridge(config)

    # Camera intrinsics for MuJoCo renderer
    # MuJoCo default FOV is 45 degrees; fx = (width/2) / tan(fov/2)
    # fx = 160 / tan(22.5 deg) ~= 386.37
    w, h = config.resolution
    fov_rad = math.radians(45.0)
    fx = (w / 2.0) / math.tan(fov_rad / 2.0)
    intrinsics = CameraIntrinsics(
        fx=fx, fy=fx, cx=w / 2.0, cy=h / 2.0, width=w, height=h
    )

    slam = SLAMPipeline(intrinsics)
    octomap = OctoMapBuilder(resolution=args.octomap_resolution)
    gt_collector = GroundTruthCollector()
    viz = RerunVisualizer() if not args.no_viz else None

    controller = create_controller(args.control)
    if hasattr(controller, "start"):
        controller.start()

    print(f"Starting SLAM with {args.control} control...")
    print(f"Max steps: {args.max_steps}")
    print("Press Ctrl+C to stop\n")

    try:
        # ------------------------------------------------------------------
        # Start simulation -- first frame
        # ------------------------------------------------------------------
        frame = bridge.start()
        gt_collector.record(frame)

        for step_i in range(args.max_steps):
            # Get velocity from controller
            if args.control == "teleop":
                linear, angular = controller.get_velocity()
            elif args.control == "waypoint":
                current_pose = (
                    slam.slam_poses[-1] if slam.slam_poses else np.eye(4)
                )
                linear, angular = controller.get_velocity(current_pose)
                if controller.is_complete:
                    print("All waypoints reached.")
                    break
            elif args.control == "random":
                linear, angular = controller.get_velocity(frame.sim_time)

            # Step simulation
            bridge.set_velocity(linear, angular)
            frame = bridge.step()
            gt_collector.record(frame)

            # Process through SLAM
            slam_pose = slam.process_frame(frame)

            # Update OctoMap periodically
            if (
                step_i % args.octomap_interval == 0
                and slam.num_frames_processed > 0
            ):
                cloud_points = slam.get_cloud_points()
                if len(cloud_points) > 0:
                    sensor_origin = slam_pose[:3, 3]
                    octomap.insert_scan(cloud_points, sensor_origin)

            # Visualize (reduce frequency for performance)
            if viz is not None:
                viz.log_frame(frame)
                viz.log_robot_pose(slam_pose)
                if step_i % 10 == 0:
                    cloud_pts = slam.get_cloud_points()
                    cloud_colors = slam.get_cloud_colors()
                    if len(cloud_pts) > 0:
                        viz.log_point_cloud(cloud_pts, cloud_colors)
                    viz.log_trajectory(slam.slam_poses)
                    voxels = octomap.get_occupied_voxels()
                    if len(voxels) > 0:
                        viz.log_occupancy_grid(voxels, octomap.resolution)

            # Print progress
            if step_i % 50 == 0:
                print(
                    f"Step {step_i}: "
                    f"cloud={len(slam.get_cloud_points())} pts, "
                    f"voxels={octomap.num_occupied}, "
                    f"pose=[{slam_pose[0, 3]:.2f}, "
                    f"{slam_pose[1, 3]:.2f}, "
                    f"{slam_pose[2, 3]:.2f}]"
                )

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        # ------------------------------------------------------------------
        # Compute and print drift metrics
        # ------------------------------------------------------------------
        if len(gt_collector) >= 2 and len(slam.slam_poses) >= 2:
            print("\n=== Drift Metrics ===")
            try:
                metrics = compute_drift_metrics(
                    slam_poses=slam.slam_poses,
                    gt_poses=gt_collector.poses,
                    timestamps=gt_collector.timestamps,
                )
                print(f"ATE RMSE: {metrics['ate_rmse']:.4f} m")
                print(f"ATE Mean: {metrics['ate_mean']:.4f} m")
                print(f"RPE RMSE: {metrics['rpe_rmse']:.4f} m")
                print(f"RPE Mean: {metrics['rpe_mean']:.4f} m")
            except Exception as e:
                print(f"Could not compute drift metrics: {e}")

        print(
            f"\nFinal stats: {slam.num_frames_processed} frames, "
            f"{len(slam.get_cloud_points())} cloud points, "
            f"{octomap.num_occupied} occupied voxels"
        )

        # Cleanup
        if hasattr(controller, "stop"):
            controller.stop()
        bridge.stop()
        print("Done.")


if __name__ == "__main__":
    main()
