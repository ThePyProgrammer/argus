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
    | 'detections'
    | 'scene_description'
    | 'color_mode_ack'
    | 'slam_param_ack'
    | 'slam_restart_complete';
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
