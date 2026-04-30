import { create } from 'zustand';
import type {
  Detection3DEnvelope,
  Detection3DItem,
  PlatformMetadata,
  RobotRuntimeStatusPayload,
} from '../utils/messageTypes';

// Re-export so consumers can `import type { Detection3DEnvelope } from '../stores/robotStore'`
export type { Detection3DEnvelope, Detection3DItem };

export interface RobotInfo {
  id: string;
  colorIndex: number;
  position: [number, number, number];
  rotation: number[]; // 9-element flat 3x3
  coveragePct: number;
  voxelCount: number;
  action: string; // "exploring" | "idle" | "stuck"
  cameraUrl: string | null;
  depthUrl: string | null;
  trajectory: number[][]; // list of [x,y,z]
  trajectoryAlphas: number[];
  detections_3d: Detection3DEnvelope | null;
  sceneDescription: string | null;
  sceneObjects: string[];
  trackingStatus: string; // "ok" | "lost" | "initializing" | "relocalizing"
  bodyYaw: number; // MuJoCo body heading in radians
  platform: string;
  platformMetadata: PlatformMetadata | null;
  runtimeState: string;
  fallReason: string;
  disabled: boolean;
  controllerHealth: Record<string, unknown> | null;
  collisionCount: number;
  nearMissCount: number;
}

export interface RobotStoreState {
  robots: Map<string, RobotInfo>;
  pointCloudPositions: number[][]; // accumulated positions
  pointCloudColors: number[][]; // accumulated colors
  colorMode: 'robot_tint' | 'true_rgb';
  totalCoverage: number;
  mergeCount: number;
  elapsed: number;

  setRobotList: (ids: string[], platforms?: Record<string, PlatformMetadata>) => void;
  updatePose: (
    robotId: string,
    position: [number, number, number],
    rotation: number[],
    trackingStatus?: string,
    bodyYaw?: number,
  ) => void;
  updateStats: (stats: {
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
  }) => void;
  appendCloudDelta: (positions: number[][], colors?: number[][]) => void;
  setCloudFull: (positions: number[][], colors?: number[][]) => void;
  setCameraUrl: (robotId: string, url: string) => void;
  setDepthUrl: (robotId: string, url: string) => void;
  updateTrajectory: (
    robotId: string,
    positions: number[][],
    alphas: number[],
  ) => void;
  setColorMode: (mode: 'robot_tint' | 'true_rgb') => void;
  updateDetections: (robotId: string, envelope: Detection3DEnvelope | null) => void;
  updateSceneDescription: (robotId: string, text: string, objects: string[]) => void;
}

export const useRobotStore = create<RobotStoreState>((set, get) => ({
  robots: new Map<string, RobotInfo>(),
  pointCloudPositions: [],
  pointCloudColors: [],
  colorMode: 'robot_tint',
  totalCoverage: 0,
  mergeCount: 0,
  elapsed: 0,

  setRobotList: (ids: string[], platforms: Record<string, PlatformMetadata> = {}) => {
    const robots = new Map<string, RobotInfo>();
    ids.forEach((id, index) => {
      const existing = get().robots.get(id);
      const platformMetadata = platforms[id] ?? existing?.platformMetadata ?? null;
      robots.set(id, {
        id,
        colorIndex: index,
        position: existing?.position ?? [0, 0, 0],
        rotation: existing?.rotation ?? [1, 0, 0, 0, 1, 0, 0, 0, 1],
        coveragePct: existing?.coveragePct ?? 0,
        voxelCount: existing?.voxelCount ?? 0,
        action: existing?.action ?? 'idle',
        cameraUrl: existing?.cameraUrl ?? null,
        depthUrl: existing?.depthUrl ?? null,
        trajectory: existing?.trajectory ?? [],
        trajectoryAlphas: existing?.trajectoryAlphas ?? [],
        detections_3d: existing?.detections_3d ?? null,
        sceneDescription: existing?.sceneDescription ?? null,
        sceneObjects: existing?.sceneObjects ?? [],
        trackingStatus: existing?.trackingStatus ?? 'ok',
        bodyYaw: existing?.bodyYaw ?? 0,
        platform: platformMetadata?.name ?? existing?.platform ?? 'go2',
        platformMetadata,
        runtimeState: existing?.runtimeState ?? 'standing',
        fallReason: existing?.fallReason ?? 'none',
        disabled: existing?.disabled ?? false,
        controllerHealth: existing?.controllerHealth ?? null,
        collisionCount: existing?.collisionCount ?? 0,
        nearMissCount: existing?.nearMissCount ?? 0,
      });
    });
    set({ robots });
  },

  updatePose: (
    robotId: string,
    position: [number, number, number],
    rotation: number[],
    trackingStatus?: string,
    bodyYaw?: number,
  ) => {
    const robots = new Map(get().robots);
    const robot = robots.get(robotId);
    if (robot) {
      robots.set(robotId, {
        ...robot,
        position,
        rotation,
        trackingStatus: trackingStatus ?? robot.trackingStatus,
        bodyYaw: bodyYaw ?? robot.bodyYaw,
      });
      set({ robots });
    }
  },

  updateStats: (stats) => {
    const robots = new Map(get().robots);
    for (const [robotId, robotStats] of Object.entries(stats.robots)) {
      const robot = robots.get(robotId);
      if (robot) {
        const runtime = robotStats.runtime_status ?? null;
        const platformMetadata = robotStats.platform ?? robot.platformMetadata;
        robots.set(robotId, {
          ...robot,
          coveragePct: robotStats.coverage_pct,
          voxelCount: robotStats.voxel_count,
          action: runtime?.state ?? robotStats.action,
          platform: platformMetadata?.name ?? robot.platform,
          platformMetadata,
          runtimeState: runtime?.state ?? robot.runtimeState,
          fallReason: runtime?.fall_reason ?? robot.fallReason,
          disabled: runtime?.disabled ?? robot.disabled,
          controllerHealth: runtime?.controller_health ?? robot.controllerHealth,
          collisionCount: runtime?.collision_count ?? robot.collisionCount,
          nearMissCount: runtime?.near_miss_count ?? robot.nearMissCount,
        });
      }
    }
    set({
      robots,
      totalCoverage: stats.total_coverage,
      mergeCount: stats.merge_count,
      elapsed: stats.elapsed,
    });
  },

  appendCloudDelta: (positions: number[][], colors?: number[][]) => {
    set((state) => ({
      pointCloudPositions: [...state.pointCloudPositions, ...positions],
      pointCloudColors: [
        ...state.pointCloudColors,
        ...(colors ?? positions.map(() => [128, 128, 128])),
      ],
    }));
  },

  setCloudFull: (positions: number[][], colors?: number[][]) => {
    set({
      pointCloudPositions: positions,
      pointCloudColors:
        colors ?? positions.map(() => [128, 128, 128]),
    });
  },

  setCameraUrl: (robotId: string, url: string) => {
    const robots = new Map(get().robots);
    const robot = robots.get(robotId);
    if (robot) {
      // Revoke previous blob URL to prevent memory leak
      if (robot.cameraUrl) {
        URL.revokeObjectURL(robot.cameraUrl);
      }
      robots.set(robotId, { ...robot, cameraUrl: url });
      set({ robots });
    }
  },

  setDepthUrl: (robotId: string, url: string) => {
    const robots = new Map(get().robots);
    const robot = robots.get(robotId);
    if (robot) {
      if (robot.depthUrl) {
        URL.revokeObjectURL(robot.depthUrl);
      }
      robots.set(robotId, { ...robot, depthUrl: url });
      set({ robots });
    }
  },

  updateTrajectory: (
    robotId: string,
    positions: number[][],
    alphas: number[],
  ) => {
    const robots = new Map(get().robots);
    const robot = robots.get(robotId);
    if (robot) {
      robots.set(robotId, {
        ...robot,
        trajectory: positions,
        trajectoryAlphas: alphas,
      });
      set({ robots });
    }
  },

  setColorMode: (mode: 'robot_tint' | 'true_rgb') => {
    set({ colorMode: mode });
  },

  updateDetections: (robotId, envelope) => {
    set((state) => {
      const robots = new Map(state.robots);
      const robot = robots.get(robotId);
      if (robot) {
        robots.set(robotId, { ...robot, detections_3d: envelope });
      }
      return { robots };
    });
  },

  updateSceneDescription: (robotId, text, objects) => {
    set((state) => {
      const robots = new Map(state.robots);
      const robot = robots.get(robotId);
      if (robot) {
        robots.set(robotId, { ...robot, sceneDescription: text, sceneObjects: objects });
      }
      return { robots };
    });
  },
}));
