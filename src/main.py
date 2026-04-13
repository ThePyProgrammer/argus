#!/usr/bin/env python3
# Suppress NNPACK C++ warnings before any imports
import os as _os
_os.environ["NNPACK_DISABLE"] = "1"
_os.environ["TORCH_CPP_LOG_LEVEL"] = "ERROR"

import src._thread_config  # noqa: F401 -- sets OMP/MKL/torch threads before any torch import (D-14)

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
import logging
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np
import rerun as rr
import uvicorn

from backend.web.server import create_app
from src.bridge.cloud_config import CLOUD_CONFIGS, get_active_config, set_active_config
from src.bridge.env_config import MuJoCoEnvConfig
from src.bridge.multi_bridge import MultiRobotBridge
from src.bridge.multi_robot_config import MultiRobotConfig
from src.bridge.sensor_types import CameraIntrinsics
from src.bridge.sim_bridge import MuJoCoBridge
from src.control.random_walk import RandomWalkController
from src.control.waypoint_runner import WaypointRunner
from src.coordination.coordinator import Coordinator
from src.coordination.robot_instance import RobotInstance
from src.coordination.spawn import generate_robot_ids, generate_spawn_positions
from src.exploration.config import ExplorationConfig
from src.exploration.exploration_loop import ExplorationLoop
from src.mcp.server import configure as configure_mcp, mcp_endpoint
from src.metrics.drift_metrics import compute_drift_metrics
from src.metrics.ground_truth import GroundTruthCollector
from src.slam.octomap_builder import OctoMapBuilder
from src.slam.registry import SLAMRegistry
import src.slam.backends  # noqa: F401 -- triggers backend registration
from src.viz.multi_robot_viz import MultiRobotVisualizer
from src.viz.rerun_viz import RerunVisualizer

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Single-robot SLAM in MuJoCo")
    parser.add_argument(
        "--control",
        choices=["teleop", "waypoint", "random", "explore", "multi", "web"],
        default="web",
        help="Control mode (default: web)",
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
        default=0,
        help="Max steps for multi-robot mode (0 = unlimited, stop with Ctrl+C)",
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
    parser.add_argument(
        "--num-robots",
        type=int,
        default=2,
        help="Number of robots (default: 2)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Web server port (default: 8000)",
    )
    return parser.parse_args()


def create_controller(mode: str) -> WaypointRunner | RandomWalkController:
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


def run_explore_mode(args: argparse.Namespace) -> None:
    """Run autonomous frontier-based exploration."""
    config = MuJoCoEnvConfig()
    bridge = MuJoCoBridge(config)

    # Camera intrinsics (same as main())
    w, h = config.resolution
    intrinsics = CameraIntrinsics.from_fov(w, h)

    slam = SLAMRegistry.create("icp", intrinsics=intrinsics)
    octomap = OctoMapBuilder(resolution=args.octomap_resolution)

    explore_config = ExplorationConfig(
        max_steps=args.explore_max_steps,
        rescan_distance_m=args.explore_rescan_distance,
        voxel_resolution=args.octomap_resolution,
    )

    loop = ExplorationLoop(bridge=bridge, slam=slam, octomap=octomap, config=explore_config)

    print("Starting autonomous exploration...")
    logger.info("Max steps: %d", explore_config.max_steps)
    logger.info("Rescan distance: %.1fm", explore_config.rescan_distance_m)
    logger.info("Voxel resolution: %.2fm", explore_config.voxel_resolution)
    logger.info("Press Ctrl+C to stop")

    try:
        result = loop.run()
    except KeyboardInterrupt:
        logger.info("Exploration interrupted by user.")
        result = None

    # Log results
    if result is not None:
        logger.info("=== Exploration Complete ===")
        logger.info("Terminated: %s", result.terminated_reason)
        logger.info("Total steps: %d", result.total_steps)
        logger.info("Coverage (frontier exhaustion): %.1f%%", result.final_coverage_pct)
        logger.info("Coverage (bounding box): %.1f%%", result.final_bbox_coverage_pct)
        logger.info("Remaining frontiers: %d", result.final_frontier_count)

    explore_cloud, _ = slam.get_global_cloud()
    logger.info(
        "Final stats: %d frames, %d cloud points, %d occupied voxels",
        slam.num_frames_processed,
        len(explore_cloud),
        octomap.num_occupied,
    )

    bridge.stop()
    print("Done.")


def run_multi_mode(args: argparse.Namespace) -> None:
    """Run two-robot coordinated exploration with map merging."""
    scene = args.scene
    n_robots = args.num_robots
    robot_ids = generate_robot_ids(n_robots)
    spawn_positions = generate_spawn_positions(robot_ids, scene)

    config = MultiRobotConfig(
        robot_ids=robot_ids,
        spawn_positions=spawn_positions,
        boot_phase_steps=args.multi_boot_steps,
        scene=scene,
    )
    bridge = MultiRobotBridge(config)

    # Camera intrinsics (same as single-robot mode)
    w, h = config.resolution
    intrinsics = CameraIntrinsics.from_fov(w, h)

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
    if args.static:
        coordinator.set_freeze_motion(True)

    print("Starting multi-robot exploration...")
    logger.info("Robots: %s", config.robot_ids)
    logger.info("Spawn positions: %s", config.spawn_positions)
    logger.info("Boot phase: %d steps", config.boot_phase_steps)
    logger.info("Max steps: %d", args.multi_max_steps)
    logger.info("Press Ctrl+C to stop")

    try:
        result = coordinator.run(max_steps=args.multi_max_steps)
    except KeyboardInterrupt:
        logger.info("Multi-robot exploration interrupted.")
        result = None

    if result is not None:
        logger.info("=== Multi-Robot Exploration Complete ===")
        logger.info("Terminated: %s", result.terminated_reason)
        logger.info("Total steps: %d", result.total_steps)
        logger.info("Merge count: %d", result.merge_count)
        logger.info("Merged voxels: %d", result.merged_voxel_count)
        for rid, count in result.per_robot_voxels.items():
            logger.info("  %s: %d voxels", rid, count)

    # Keep MuJoCo viewer open until user closes it
    viewer_handle = getattr(bridge, '_viewer_handle', None)
    if viewer_handle is not None:
        logger.info("Exploration complete. Close the MuJoCo viewer window to exit.")
        try:
            while viewer_handle.is_running():
                viewer_handle.sync()
                time.sleep(0.03)  # ~30fps
        except Exception:
            pass  # viewer may already be closed

    bridge.stop()

    # Clean shutdown of Rerun to avoid gRPC segfault on exit
    rr.disconnect()
    time.sleep(0.5)
    print("Done.")


def run_web_mode(args: argparse.Namespace) -> None:
    """Run the Argus web interface: FastAPI + MuJoCo simulation together.

    Starts the multi-robot simulation in a background thread and serves
    the React frontend via FastAPI.
    """

    scene = args.scene
    n_robots = args.num_robots
    robot_ids = generate_robot_ids(n_robots)
    spawn_positions = generate_spawn_positions(robot_ids, scene)

    config_kwargs = {
        "robot_ids": robot_ids,
        "spawn_positions": spawn_positions,
        "boot_phase_steps": args.multi_boot_steps,
        "scene": scene,
        }
    config = MultiRobotConfig(**config_kwargs)
    bridge = MultiRobotBridge(config)

    # Camera intrinsics
    w, h = config.resolution
    intrinsics = CameraIntrinsics.from_fov(w, h)

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
        for rid, robot in robots.items():
            robot.slam.reset()
            robot.octomap.reset()
        coordinator.reset_merger()
        logger.info("[cloud config] SLAM and OctoMap reset for all robots")

    configure_mcp(coordinator, list(config.robot_ids))

    app, streaming_viz = create_app(
        list(config.robot_ids),
        command_cb=coordinator.handle_command,
        slam_reset_cb=_reset_slam,
        mcp_endpoint=mcp_endpoint,
        cloud_config_fns={
            "get": get_active_config,
            "set": set_active_config,
            "configs": lambda: CLOUD_CONFIGS,
        },
    )
    coordinator.set_viz(streaming_viz)
    if args.static:
        coordinator.set_freeze_motion(True)
    logger.info("MCP endpoint available at http://localhost:%d/mcp", args.port)

    # Build React frontend
    frontend_dir = Path(__file__).parent.parent / "frontend"
    if (frontend_dir / "package.json").exists():
        logger.info("Building React frontend...")
        try:
            subprocess.run(
                ["npm", "run", "build"],
                cwd=str(frontend_dir),
                check=True,
                capture_output=True,
                timeout=120,
            )
            logger.info("Frontend build complete.")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.warning("Frontend build failed (%s). Serving pre-built files if available.", e)

    max_steps = args.multi_max_steps
    _restart_lock = threading.Lock()

    # Start simulation in background thread with restart support
    def _run_simulation_loop():
        nonlocal bridge, robots, coordinator, streaming_viz

        while True:
            try:
                result = coordinator.run(max_steps=max_steps)
                logger.info(
                    "Simulation complete: %s, %d steps, %d merges",
                    result.terminated_reason, result.total_steps, result.merge_count,
                )
            except Exception as e:
                logger.warning("Simulation error: %s", e)

            # Check if restart was requested
            if not coordinator.restart_requested:
                break

            logger.info("=== RESTARTING SIMULATION ===")

            with _restart_lock:
                coordinator._restarting = True
                new_positions = coordinator.restart_positions

                # Stop old bridge
                try:
                    bridge.stop()
                except Exception:
                    pass  # best-effort cleanup during restart

                # Update config with new or random positions
                if new_positions:
                    config.spawn_positions = {
                        rid: (float(p[0]), float(p[1]), float(p[2]))
                        for rid, p in new_positions.items()
                        if rid in config.robot_ids
                    }
                elif config.scene != "flat":
                    config.spawn_positions = generate_spawn_positions(config.robot_ids, config.scene)
                logger.info("Spawn positions: %s", config.spawn_positions)

                # Read pending config: pipeline graph config takes priority over individual selections
                pipeline_config = getattr(app.state, "pending_pipeline_config", None)
                pending_backend = getattr(app.state, "pending_slam_backend", None)
                pending_merger = getattr(app.state, "pending_merge_strategy", None)

                # Pipeline config overrides individual backend/merger selections
                if pipeline_config is not None:
                    pending_backend = pipeline_config.backend_name
                    pending_merger = pipeline_config.merger_name

                # Recreate bridge + robots
                bridge = MultiRobotBridge(config)
                robots = {}
                for rid in config.robot_ids:
                    robots[rid] = RobotInstance.create(
                        robot_id=rid,
                        bridge=bridge,
                        intrinsics=intrinsics,
                        config=explore_config,
                        spawn_position=config.spawn_positions[rid],
                        backend_name=pending_backend,
                    )

                # Create merge strategy from pending selection
                merger = None
                if pending_merger:
                    try:
                        from src.coordination.merge_registry import MergeRegistry
                        import src.coordination.merge_strategies  # noqa: F401
                        merger = MergeRegistry.create(
                            name=pending_merger,
                            spawn_transforms={
                                rid: robots[rid].spawn_transform for rid in robots
                            },
                        )
                    except (ImportError, ValueError) as exc:
                        logger.warning("Failed to create merge strategy '%s': %s", pending_merger, exc)

                coordinator.reset_for_restart(bridge, robots)
                if merger is not None:
                    coordinator._merger = merger
                coordinator._restarting = False

                # Update active backend/merger and clear pending state
                app.state.active_slam_backend = pending_backend or "icp"
                app.state.active_merge_strategy = pending_merger or "icp_union"
                app.state.pending_slam_backend = None
                app.state.pending_merge_strategy = None
                app.state.pending_pipeline_config = None

                # Reset streaming viz cloud tracking
                if streaming_viz is not None:
                    streaming_viz.reset_cloud_tracking()

                # Notify frontend that restart is complete
                if streaming_viz is not None:
                    streaming_viz._message_queue.append({
                        "type": "slam_restart_complete",
                        "payload": {},
                    })

            logger.info("Simulation restarted.")

    sim_thread = threading.Thread(target=_run_simulation_loop, daemon=True)
    sim_thread.start()

    print(f"Starting Argus at http://localhost:{args.port}")
    logger.info("Robots: %s", config.robot_ids)
    logger.info("Scene: %s", scene)
    for rid, pos in config.spawn_positions.items():
        logger.info("  %s: (%.2f, %.2f, %.2f)", rid, pos[0], pos[1], pos[2])
    logger.info("Max steps: %d", max_steps)
    logger.info("Press Ctrl+C to stop")

    try:
        uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="info")
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down Argus...")
    finally:
        coordinator.request_stop()
        sim_thread.join(timeout=5.0)
        try:
            bridge.stop()
        except RuntimeError:
            pass  # ignore dict-changed-size during cleanup
        print("Done.")


def main() -> None:
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
    intrinsics = CameraIntrinsics.from_fov(w, h)

    slam = SLAMRegistry.create("icp", intrinsics=intrinsics)
    octomap = OctoMapBuilder(resolution=args.octomap_resolution)
    gt_collector = GroundTruthCollector()
    viz = RerunVisualizer() if not args.no_viz else None

    controller = create_controller(args.control)
    if hasattr(controller, "start"):
        controller.start()

    print(f"Starting SLAM with {args.control} control...")
    logger.info("Max steps: %d", args.max_steps)
    logger.info("Press Ctrl+C to stop")

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
                poses = slam.get_poses()
                current_pose = poses[-1] if poses else np.eye(4)
                linear, angular = controller.get_velocity(current_pose)
                if controller.is_complete:
                    logger.info("All waypoints reached.")
                    break
            elif args.control == "random":
                linear, angular = controller.get_velocity(frame.sim_time)

            # Step simulation
            bridge.set_velocity(linear, angular)
            frame = bridge.step()
            gt_collector.record(frame)

            # Process through SLAM
            slam_result = slam.process_frame(frame)
            slam_pose = slam_result.pose

            # Update OctoMap periodically
            if (
                step_i % args.octomap_interval == 0
                and slam.num_frames_processed > 0
            ):
                cloud_points, _ = slam.get_global_cloud()
                if len(cloud_points) > 0:
                    sensor_origin = slam_pose[:3, 3]
                    octomap.insert_scan(cloud_points, sensor_origin)

            # Visualize (reduce frequency for performance)
            if viz is not None:
                viz.log_frame(frame)
                viz.log_robot_pose(slam_pose)
                if step_i % 10 == 0:
                    cloud_pts, cloud_colors = slam.get_global_cloud()
                    if len(cloud_pts) > 0:
                        viz.log_point_cloud(cloud_pts, cloud_colors)
                    viz.log_trajectory(slam.get_poses())
                    voxels = octomap.get_occupied_voxels()
                    if len(voxels) > 0:
                        viz.log_occupancy_grid(voxels, octomap.resolution)

            # Log progress
            if step_i % 50 == 0:
                cloud_pts_log, _ = slam.get_global_cloud()
                logger.info(
                    "Step %d: cloud=%d pts, voxels=%d, pose=[%.2f, %.2f, %.2f]",
                    step_i,
                    len(cloud_pts_log),
                    octomap.num_occupied,
                    slam_pose[0, 3],
                    slam_pose[1, 3],
                    slam_pose[2, 3],
                )

    except KeyboardInterrupt:
        logger.info("Stopping...")
    finally:
        # ------------------------------------------------------------------
        # Compute and log drift metrics
        # ------------------------------------------------------------------
        slam_poses = slam.get_poses()
        if len(gt_collector) >= 2 and len(slam_poses) >= 2:
            logger.info("=== Drift Metrics ===")
            try:
                metrics = compute_drift_metrics(
                    slam_poses=slam_poses,
                    gt_poses=gt_collector.poses,
                    timestamps=gt_collector.timestamps,
                )
                logger.info("ATE RMSE: %.4f m", metrics['ate_rmse'])
                logger.info("ATE Mean: %.4f m", metrics['ate_mean'])
                logger.info("RPE RMSE: %.4f m", metrics['rpe_rmse'])
                logger.info("RPE Mean: %.4f m", metrics['rpe_mean'])
            except Exception as e:
                logger.warning("Could not compute drift metrics: %s", e)

        final_cloud, _ = slam.get_global_cloud()
        logger.info(
            "Final stats: %d frames, %d cloud points, %d occupied voxels",
            slam.num_frames_processed,
            len(final_cloud),
            octomap.num_occupied,
        )

        # Cleanup
        if hasattr(controller, "stop"):
            controller.stop()
        bridge.stop()
        print("Done.")


if __name__ == "__main__":
    main()
