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
  --control explore   : Autonomous frontier-based exploration
  --control multi     : Two-robot coordinated exploration with map merging
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
        choices=["teleop", "waypoint", "random", "explore", "multi", "web"],
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
    parser.add_argument(
        "--explore-max-steps",
        type=int,
        default=10000,
        help="Max steps for explore mode (default: 10000)",
    )
    parser.add_argument(
        "--explore-rescan-distance",
        type=float,
        default=2.0,
        help="Frontier rescan distance in meters (default: 2.0)",
    )
    parser.add_argument(
        "--multi-max-steps",
        type=int,
        default=10000,
        help="Max steps for multi-robot mode (default: 10000)",
    )
    parser.add_argument(
        "--multi-boot-steps",
        type=int,
        default=200,
        help="Boot phase steps for multi-robot mode (default: 200)",
    )
    parser.add_argument(
        "--scene",
        choices=["flat", "office"],
        default="flat",
        help="Scene type for multi-robot mode (default: flat)",
    )
    parser.add_argument(
        "--static",
        action="store_true",
        help="Keep robots stationary (SLAM still runs, robots don't walk)",
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


def run_explore_mode(args):
    """Run autonomous frontier-based exploration."""
    import math

    from src.exploration.config import ExplorationConfig
    from src.exploration.exploration_loop import ExplorationLoop

    config = MuJoCoEnvConfig()
    bridge = MuJoCoBridge(config)

    # Camera intrinsics (same as main())
    w, h = config.resolution
    fov_rad = math.radians(45.0)
    fx = h / (2.0 * math.tan(fov_rad / 2.0))  # fovy is vertical FOV → use height
    intrinsics = CameraIntrinsics(
        fx=fx, fy=fx, cx=w / 2.0, cy=h / 2.0, width=w, height=h
    )

    slam = SLAMPipeline(intrinsics)
    octomap = OctoMapBuilder(resolution=args.octomap_resolution)

    explore_config = ExplorationConfig(
        max_steps=args.explore_max_steps,
        rescan_distance_m=args.explore_rescan_distance,
        voxel_resolution=args.octomap_resolution,
    )

    loop = ExplorationLoop(bridge=bridge, slam=slam, octomap=octomap, config=explore_config)

    print(f"Starting autonomous exploration...")
    print(f"Max steps: {explore_config.max_steps}")
    print(f"Rescan distance: {explore_config.rescan_distance_m}m")
    print(f"Voxel resolution: {explore_config.voxel_resolution}m")
    print("Press Ctrl+C to stop\n")

    try:
        result = loop.run()
    except KeyboardInterrupt:
        print("\nExploration interrupted by user.")
        result = None

    # Print results
    if result is not None:
        print(f"\n=== Exploration Complete ===")
        print(f"Terminated: {result.terminated_reason}")
        print(f"Total steps: {result.total_steps}")
        print(f"Coverage (frontier exhaustion): {result.final_coverage_pct:.1f}%")
        print(f"Coverage (bounding box): {result.final_bbox_coverage_pct:.1f}%")
        print(f"Remaining frontiers: {result.final_frontier_count}")

    # Drift metrics
    if len(slam.slam_poses) >= 2:
        print("\n=== Drift Metrics ===")
        try:
            # Full GT collection happens inside ExplorationLoop
            # For now just report SLAM stats
            pass
        except Exception as e:
            print(f"Could not compute drift metrics: {e}")

    print(
        f"\nFinal stats: {slam.num_frames_processed} frames, "
        f"{len(slam.get_cloud_points())} cloud points, "
        f"{octomap.num_occupied} occupied voxels"
    )

    bridge.stop()
    print("Done.")


def run_multi_mode(args):
    """Run two-robot coordinated exploration with map merging."""
    import math

    from src.coordination.multi_robot_config import MultiRobotConfig
    from src.bridge.multi_bridge import MultiRobotBridge
    from src.coordination.robot_instance import RobotInstance
    from src.coordination.coordinator import Coordinator
    from src.bridge.sensor_types import CameraIntrinsics
    from src.exploration.config import ExplorationConfig
    from src.viz.multi_robot_viz import MultiRobotVisualizer

    scene = getattr(args, 'scene', 'office')
    config_kwargs = {"boot_phase_steps": args.multi_boot_steps, "scene": scene}
    if scene == "flat":
        config_kwargs["spawn_positions"] = {"robot_a": (0.0, 0.0, 0.3), "robot_b": (5.0, 0.0, 0.3)}
    else:
        import random, math
        # Place robot_a randomly, then robot_b at a forced distance away
        spawn_range = 8.0  # ±8m from origin
        ax, ay = random.uniform(-spawn_range, spawn_range), random.uniform(-spawn_range, spawn_range)
        angle = random.uniform(0, 2 * math.pi)
        dist = random.uniform(5.0, 10.0)
        bx = ax + dist * math.cos(angle)
        by = ay + dist * math.sin(angle)
        config_kwargs["spawn_positions"] = {"robot_a": (ax, ay, 0.3), "robot_b": (bx, by, 0.3)}
    config = MultiRobotConfig(**config_kwargs)
    bridge = MultiRobotBridge(config)

    # Camera intrinsics (same as single-robot mode)
    w, h = config.resolution
    fov_rad = math.radians(45.0)
    fx = h / (2.0 * math.tan(fov_rad / 2.0))  # fovy is vertical FOV → use height
    intrinsics = CameraIntrinsics(fx=fx, fy=fx, cx=w / 2.0, cy=h / 2.0, width=w, height=h)

    explore_config = ExplorationConfig(
        max_steps=args.multi_max_steps,
        rescan_distance_m=args.explore_rescan_distance,
        voxel_resolution=args.octomap_resolution,
    )

    robots = {}
    for rid in config.robot_ids:
        robots[rid] = RobotInstance.create(
            robot_id=rid,
            bridge=bridge,
            intrinsics=intrinsics,
            config=explore_config,
            spawn_position=config.spawn_positions[rid],
        )

    viz = MultiRobotVisualizer(app_name="multi_robot_viz")
    coordinator = Coordinator(bridge=bridge, robots=robots, config=config, viz=viz)
    if getattr(args, 'static', False):
        coordinator._static = True

    print(f"Starting multi-robot exploration...")
    print(f"Robots: {config.robot_ids}")
    print(f"Spawn positions: {config.spawn_positions}")
    print(f"Boot phase: {config.boot_phase_steps} steps")
    print(f"Max steps: {args.multi_max_steps}")
    print("Press Ctrl+C to stop\n")

    try:
        result = coordinator.run(max_steps=args.multi_max_steps)
    except KeyboardInterrupt:
        print("\nMulti-robot exploration interrupted.")
        result = None

    if result is not None:
        print(f"\n=== Multi-Robot Exploration Complete ===")
        print(f"Terminated: {result['terminated_reason']}")
        print(f"Total steps: {result['total_steps']}")
        print(f"Merge count: {result['merge_count']}")
        print(f"Merged voxels: {result['merged_voxel_count']}")
        for rid, count in result['per_robot_voxels'].items():
            print(f"  {rid}: {count} voxels")

    # Keep MuJoCo viewer open until user closes it
    import time
    viewer_handle = getattr(bridge, '_viewer_handle', None)
    if viewer_handle is not None:
        print("\nExploration complete. Close the MuJoCo viewer window to exit.")
        try:
            while viewer_handle.is_running():
                viewer_handle.sync()
                time.sleep(0.03)  # ~30fps
        except (AttributeError, Exception):
            pass

    bridge.stop()

    # Clean shutdown of Rerun to avoid gRPC segfault on exit
    import rerun as rr
    rr.disconnect()
    time.sleep(0.5)
    print("Done.")


def run_web_mode(args):
    """Run the C2 web interface: FastAPI + MuJoCo simulation together.

    Starts the multi-robot simulation in a background thread and serves
    the React C2 frontend via FastAPI at http://localhost:8000.
    """
    import math
    import subprocess
    import threading

    import uvicorn

    from src.coordination.multi_robot_config import MultiRobotConfig
    from src.bridge.multi_bridge import MultiRobotBridge
    from src.coordination.robot_instance import RobotInstance
    from src.coordination.coordinator import Coordinator
    from src.bridge.sensor_types import CameraIntrinsics
    from src.exploration.config import ExplorationConfig
    pass  # web server module imported below via configure_app

    scene = getattr(args, "scene", "office")
    config_kwargs = {"boot_phase_steps": args.multi_boot_steps, "scene": scene}
    if scene == "flat":
        config_kwargs["spawn_positions"] = {"robot_a": (0.0, 0.0, 0.3), "robot_b": (5.0, 0.0, 0.3)}
    else:
        import random, math
        # Place robot_a randomly, then robot_b at a forced distance away
        spawn_range = 8.0  # ±8m from origin
        ax, ay = random.uniform(-spawn_range, spawn_range), random.uniform(-spawn_range, spawn_range)
        angle = random.uniform(0, 2 * math.pi)
        dist = random.uniform(5.0, 10.0)
        bx = ax + dist * math.cos(angle)
        by = ay + dist * math.sin(angle)
        config_kwargs["spawn_positions"] = {"robot_a": (ax, ay, 0.3), "robot_b": (bx, by, 0.3)}
    config = MultiRobotConfig(**config_kwargs)
    bridge = MultiRobotBridge(config)

    # Camera intrinsics
    w, h = config.resolution
    fov_rad = math.radians(45.0)
    fx = h / (2.0 * math.tan(fov_rad / 2.0))  # fovy is vertical FOV → use height
    intrinsics = CameraIntrinsics(fx=fx, fy=fx, cx=w / 2.0, cy=h / 2.0, width=w, height=h)

    explore_config = ExplorationConfig(
        max_steps=args.multi_max_steps,
        rescan_distance_m=args.explore_rescan_distance,
        voxel_resolution=args.octomap_resolution,
    )

    robots = {}
    for rid in config.robot_ids:
        robots[rid] = RobotInstance.create(
            robot_id=rid,
            bridge=bridge,
            intrinsics=intrinsics,
            config=explore_config,
            spawn_position=config.spawn_positions[rid],
        )

    # Configure shared state BEFORE coordinator so we can pass command_handler
    coordinator = Coordinator(bridge=bridge, robots=robots, config=config)

    def _reset_slam():
        """Reset SLAM and OctoMap for all robots when cloud config changes."""
        import open3d as o3d
        for rid, robot in robots.items():
            robot.slam._global_cloud = o3d.geometry.PointCloud()
            robot.slam._slam_poses.clear()
            robot.slam._prev_cloud = None
            robot.slam._current_pose = np.eye(4)
            robot.octomap._accumulated_cloud = o3d.geometry.PointCloud()
        # Also clear the merger's last merged voxels
        if hasattr(coordinator, '_merger'):
            coordinator._merger.last_merged_voxels = np.empty((0, 3))
        print("[cloud config] SLAM and OctoMap reset for all robots")

    from backend.web.server import create_app
    app, streaming_viz = create_app(
        list(config.robot_ids),
        command_cb=coordinator._command_handler,
        slam_reset_cb=_reset_slam,
    )
    coordinator._viz = streaming_viz
    if getattr(args, 'static', False):
        coordinator._static = True

    # Build React frontend
    from pathlib import Path
    frontend_dir = Path(__file__).parent.parent / "frontend"
    if (frontend_dir / "package.json").exists():
        print("Building React frontend...")
        try:
            subprocess.run(
                ["npm", "run", "build"],
                cwd=str(frontend_dir),
                check=True,
                capture_output=True,
            )
            print("Frontend build complete.")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"Warning: frontend build failed ({e}). Serving pre-built files if available.")

    max_steps = args.multi_max_steps

    # Start simulation in background thread
    def _run_simulation():
        try:
            result = coordinator.run(max_steps=max_steps)
            print(f"\nSimulation complete: {result['terminated_reason']}, "
                  f"{result['total_steps']} steps, {result['merge_count']} merges")
        except Exception as e:
            print(f"\nSimulation error: {e}")

    sim_thread = threading.Thread(target=_run_simulation, daemon=True)
    sim_thread.start()

    print(f"\nC2 Interface running at http://localhost:8000")
    print(f"Robots: {config.robot_ids}")
    print(f"Scene: {scene}")
    for rid, pos in config.spawn_positions.items():
        print(f"  {rid}: ({pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f})")
    print(f"Max steps: {max_steps}")
    print("Press Ctrl+C to stop\n")

    try:
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
    except (KeyboardInterrupt, SystemExit):
        print("\nShutting down C2 interface...")
    finally:
        coordinator._should_stop = True
        sim_thread.join(timeout=5.0)
        try:
            bridge.stop()
        except RuntimeError:
            pass  # ignore dict-changed-size during cleanup
        print("Done.")


def main():
    """Run the single-robot SLAM loop."""
    args = parse_args()

    if args.control == "web":
        run_web_mode(args)
        return

    if args.control == "multi":
        run_multi_mode(args)
        return

    if args.control == "explore":
        run_explore_mode(args)
        return

    # ------------------------------------------------------------------
    # Initialize components
    # ------------------------------------------------------------------
    config = MuJoCoEnvConfig()
    bridge = MuJoCoBridge(config)

    # Camera intrinsics for MuJoCo renderer
    # MuJoCo fovy is VERTICAL FOV: f = height / (2 * tan(fovy/2))
    # f = 240 / (2 * tan(22.5°)) = 289.71
    w, h = config.resolution
    fov_rad = math.radians(45.0)
    fx = h / (2.0 * math.tan(fov_rad / 2.0))  # fovy is vertical FOV → use height
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
