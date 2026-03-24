import { create } from 'zustand';

export interface Detection {
  class: string;
  confidence: number;
  bbox: number[];
  pos_3d: number[] | null;
  depth: number | null;
}

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
  detections: Detection[];
  sceneDescription: string | null;
  sceneObjects: string[];
  trackingStatus: string; // "ok" | "lost" | "initializing" | "relocalizing"
  bodyYaw: number; // MuJoCo body heading in radians
}

export interface RobotStoreState {
  robots: Map<string, RobotInfo>;
  pointCloudPositions: number[][]; // accumulated positions
  pointCloudColors: number[][]; // accumulated colors
  colorMode: 'robot_tint' | 'true_rgb';
  totalCoverage: number;
  mergeCount: number;
  elapsed: number;

  setRobotList: (ids: string[]) => void;
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
      { coverage_pct: number; voxel_count: number; action: string }
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
  updateDetections: (robotId: string, detections: Detection[]) => void;
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

  setRobotList: (ids: string[]) => {
    const robots = new Map<string, RobotInfo>();
    ids.forEach((id, index) => {
      const existing = get().robots.get(id);
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
        detections: existing?.detections ?? [],
        sceneDescription: existing?.sceneDescription ?? null,
        sceneObjects: existing?.sceneObjects ?? [],
        trackingStatus: existing?.trackingStatus ?? 'ok',
        bodyYaw: existing?.bodyYaw ?? 0,
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
        robots.set(robotId, {
          ...robot,
          coveragePct: robotStats.coverage_pct,
          voxelCount: robotStats.voxel_count,
          action: robotStats.action,
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

  updateDetections: (robotId, detections) => {
    set((state) => {
      const robots = new Map(state.robots);
      const robot = robots.get(robotId);
      if (robot) {
        robots.set(robotId, { ...robot, detections });
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
