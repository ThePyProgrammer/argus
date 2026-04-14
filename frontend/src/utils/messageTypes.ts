/** Generic WebSocket message envelope. */
export interface WSMessage {
  type:
    | 'robot_list'
    | 'pose_update'
    | 'cloud_delta'
    | 'cloud_full'
    | 'camera_frame'
    | 'stats'
    | 'command'
    | 'trajectory'
    | 'cloud_configs'
    | 'cloud_config_ack'
    | 'detections_3d'              // D-18 cutover from legacy 'detections' (Phase 2)
    | 'detector_restart_complete'  // new Phase 2
    | 'detector_param_ack'         // new Phase 2
    | 'scene_description'
    | 'color_mode_ack'
    | 'slam_param_ack'
    | 'slam_restart_complete'
    | 'crash_fallback'
    | 'pipeline_status';
  robot_id?: string;
  payload: unknown;
}

export interface RobotListPayload {
  robots: string[];
}

export interface PoseUpdatePayload {
  position: [number, number, number];
  rotation: number[]; // 9-element flat 3x3
  tracking_status?: string; // "ok" | "lost" | "initializing" | "relocalizing"
  body_yaw?: number; // MuJoCo body heading in radians
}

export interface CloudDeltaPayload {
  positions: number[][];
  colors?: number[][];
}

export interface CloudFullPayload {
  positions: number[][];
  colors?: number[][];
}

export interface SlamMetrics {
  ate_rmse: number;
  ate_mean: number;
  rpe_rmse: number;
  rpe_mean: number;
  ms_per_frame: number;
  tracking_status: string;
}

export interface MetricHistory {
  ate_rmse: number[];
  rpe_rmse: number[];
  ms_per_frame: number[];
  timestamps: number[];
}

export interface StatsPayload {
  total_coverage: number;
  merge_count: number;
  elapsed: number;
  robots: Record<
    string,
    { coverage_pct: number; voxel_count: number; action: string }
  >;
  slam_metrics?: Record<string, SlamMetrics>;
  baseline?: Record<string, SlamMetrics> | null;
  metric_history?: Record<string, MetricHistory>;
}

export interface TrajectoryPayload {
  positions: number[][];
  alphas: number[];
}

/**
 * Single oriented 3D detection (D-09 wire shape, per Plan 01 OrientedBox3D.to_wire).
 *
 * Phase 2: MedianDepthLifter emits identity quaternion [0,0,0,1].
 * Phase 4 (DET-3D-01): PointClusterLifter will emit real OBB orientation.
 */
export interface Detection3DItem {
  center: [number, number, number];              // world-frame meters
  half_extents: [number, number, number];        // local-axis meters
  quaternion: [number, number, number, number];  // xyzw, qw >= 0 (D-06)
  class_id: number;
  class_name: string;
  score: number;
  track_id?: number;                              // omitted when null (D-07)
  bbox_xyxy?: [number, number, number, number];   // optional 2D pixel bbox for CameraFeed (Plan 01)
}

/**
 * Detections3D envelope payload (D-14 capture_pose + D-12 capture_timestamp).
 * Matches Detections3D.to_wire() from Plan 01.
 */
export interface Detection3DEnvelope {
  items: Detection3DItem[];
  capture_pose: number[];           // flat 16-float row-major (THREE.Matrix4.fromArray)
  capture_timestamp: number;        // sim time in seconds (D-12)
  image_hw: [number, number];
  metrics: {
    detector_ms: number;
    lifter_ms: number;
    n_raw: number;
    n_final: number;
  };
}

/** Payload for 'detector_restart_complete' message. */
export interface DetectorRestartCompletePayload {
  backend: string;
}

/** Payload for 'detector_param_ack' message. */
export interface DetectorParamAckPayload {
  param: string;
  status: 'applied' | 'requires_restart' | 'unknown_parameter';
  value?: unknown;
}
