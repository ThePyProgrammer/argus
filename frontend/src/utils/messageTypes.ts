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

export interface PlatformMetadata {
  name: string;
  display_name: string;
  model_dir?: string;
  model_xml?: string;
  actuator_count?: number;
  command_modes?: string[];
  footprint_radius?: number;
  dimensions?: [number, number, number];
  max_linear_speed?: number;
  max_yaw_rate?: number;
  marker_asset?: string | null;
  spawn_height?: number;
}

export interface RobotRuntimeStatusPayload {
  state: 'standing' | 'walking' | 'fallen' | 'recovering' | 'disabled';
  fall_reason: string;
  disabled: boolean;
  last_command?: {
    mode: string;
    linear: number[];
    yaw_rate: number;
    waypoint: number[] | null;
  };
  command_tracking?: Record<string, unknown>;
  controller_health?: Record<string, unknown>;
  collision_count?: number;
  near_miss_count?: number;
}

export interface RobotListPayload {
  robots: string[];
  platforms?: Record<string, PlatformMetadata>;
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
    {
      coverage_pct: number;
      voxel_count: number;
      action: string;
      platform?: PlatformMetadata | null;
      runtime_status?: RobotRuntimeStatusPayload | null;
    }
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

/** Per-robot detection metrics from DetectionMetricsTracker.get_stats_payload.
 *  Phase 6 DET-METRICS-01. Mirrors src/metrics/detection_metrics_tracker.py. */
export interface DetectionMetrics {
  inference_ms_p50: number;
  inference_ms_p95: number;
  detections_per_frame: number;
  mean_confidence: number;
  freshness_s: number;
  queue_depth: number;
  jitter_m: number;
}

/** Per-robot detection metric history arrays (ring-buffer snapshots). */
export interface DetectionMetricHistory {
  inference_ms: number[];
  det_per_frame: number[];
  confidence: number[];
  freshness: number[];
  jitter: number[];
}

/** SC#2 — per-class GT match aggregates. Mirrors backend `detection_gt_metrics[rid][class_name]`.
 *  revision 2026-04-15. */
export interface DetectionGtClass {
  /** Mean center-error over last 60 matched frames (meters). `null` until first match. */
  center_error_m: number | null;
  /** matched_count / frames_observed in [0, 1]. */
  per_class_recall: number;
}
export type DetectionGtMetrics = Record<string, DetectionGtClass>;

/** Fused cross-robot detection from DetectionFusionManager (DET-STRETCH-02). */
export interface FusedDetection {
  fused_track_id: number;
  class_name: string;
  score: number;
  center: [number, number, number];
  half_extents: [number, number, number];
  quaternion: [number, number, number, number];
  robot_ids: string[];
  source_track_ids: number[];
}

/** Semantic map object with TTL (DET-STRETCH-03). */
export interface SemanticMapObject {
  fused_track_id: number;
  class_name: string;
  center: [number, number, number];
  half_extents: [number, number, number];
  quaternion: [number, number, number, number];
  score: number;
  last_seen: number;
  ttl: number;
}

/** Semantic map delta update from server. */
export interface SemanticMapDelta {
  active: SemanticMapObject[];
  expired_ids: number[];
}

/** Per-robot backend status from GET /api/detectors/active extension (DET-STRETCH-04). */
export interface PerRobotBackendStatus {
  [robotId: string]: string;
}
