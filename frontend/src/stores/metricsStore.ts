import { create } from 'zustand';
import type { SlamMetrics, MetricHistory } from '../utils/messageTypes';

interface MetricsStoreState {
  /** Per-robot live metrics */
  perRobot: Record<string, SlamMetrics>;
  /** Baseline from last ICP session */
  baseline: Record<string, SlamMetrics> | null;
  /** View mode: "live" or "baseline" */
  viewMode: 'live' | 'baseline';
  /** Output rendering mode */
  outputMode: 'cloud' | 'voxel' | 'mesh';
  /** Whether output (point cloud / voxel grid / mesh) is hidden in the 3D scene */
  outputHidden: boolean;
  /** Per-robot metric history arrays (ring buffers from backend) */
  history: Record<string, MetricHistory>;
  /** Mesh data from server (for CTRL-07) */
  meshVertices: number[][] | null;
  meshFaces: number[][] | null;
  meshColors: number[][] | null;

  // Setters
  updateMetrics: (robotId: string, metrics: SlamMetrics) => void;
  updateAllMetrics: (
    slam_metrics: Record<string, SlamMetrics>,
    baseline: Record<string, SlamMetrics> | null,
    history: Record<string, MetricHistory>,
  ) => void;
  setBaseline: (baseline: Record<string, SlamMetrics> | null) => void;
  setViewMode: (mode: 'live' | 'baseline') => void;
  setOutputMode: (mode: 'cloud' | 'voxel' | 'mesh') => void;
  setOutputHidden: (hidden: boolean) => void;
  updateHistory: (robotId: string, history: MetricHistory) => void;
  setMeshData: (
    vertices: number[][],
    faces: number[][],
    colors?: number[][] | null,
  ) => void;
  clearMeshData: () => void;
}

export const useMetricsStore = create<MetricsStoreState>()((set) => ({
  perRobot: {},
  baseline: null,
  viewMode: 'live',
  outputMode: (() => {
    const stored = localStorage.getItem('c2-outputMode');
    return stored === 'cloud' || stored === 'voxel' || stored === 'mesh' ? stored : 'cloud';
  })(),
  outputHidden: localStorage.getItem('c2-outputHidden') === 'true',
  history: {},
  meshVertices: null,
  meshFaces: null,
  meshColors: null,

  updateMetrics: (robotId, metrics) =>
    set((state) => ({
      perRobot: { ...state.perRobot, [robotId]: metrics },
    })),

  // Single set() call with all three fields to avoid 3 re-renders per stats message
  updateAllMetrics: (slam_metrics, baseline, history) =>
    set({
      perRobot: slam_metrics,
      baseline: baseline,
      history,
    }),

  setBaseline: (baseline) => set({ baseline }),
  setViewMode: (mode) => set({ viewMode: mode }),
  setOutputMode: (mode) => {
    localStorage.setItem('c2-outputMode', mode);
    set({ outputMode: mode });
  },
  setOutputHidden: (hidden) => {
    localStorage.setItem('c2-outputHidden', String(hidden));
    set({ outputHidden: hidden });
  },
  updateHistory: (robotId, history) =>
    set((state) => ({
      history: { ...state.history, [robotId]: history },
    })),
  setMeshData: (vertices, faces, colors = null) =>
    set({ meshVertices: vertices, meshFaces: faces, meshColors: colors }),
  clearMeshData: () =>
    set({ meshVertices: null, meshFaces: null, meshColors: null }),
}));
