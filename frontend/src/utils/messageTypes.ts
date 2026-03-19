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
    | 'cloud_config_ack';
  robot_id?: string;
  payload: unknown;
}

export interface RobotListPayload {
  robots: string[];
}

export interface PoseUpdatePayload {
  position: [number, number, number];
  rotation: number[]; // 9-element flat 3x3
}

export interface CloudDeltaPayload {
  positions: number[][];
  colors?: number[][];
}

export interface CloudFullPayload {
  positions: number[][];
  colors?: number[][];
}

export interface StatsPayload {
  total_coverage: number;
  merge_count: number;
  elapsed: number;
  robots: Record<
    string,
    { coverage_pct: number; voxel_count: number; action: string }
  >;
}

export interface TrajectoryPayload {
  positions: number[][];
  alphas: number[];
}
