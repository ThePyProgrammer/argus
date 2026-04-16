import { create } from 'zustand';
import type {
  SlamMetrics,
  MetricHistory,
  DetectionMetrics,
  DetectionMetricHistory,
  DetectionGtMetrics,
  FusedDetection,
} from '../utils/messageTypes';

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
  /** Phase 6 DET-METRICS-01 — per-robot detection metrics slice */
  detectionPerRobot: Record<string, DetectionMetrics>;
  /** Phase 6 DET-METRICS-01 — per-robot detection history (ring buffers) */
  detectionHistory: Record<string, DetectionMetricHistory>;
  /** Phase 6 SC#2 revision 2026-04-15 — per-robot per-class GT aggregates */
  detectionGtPerRobot: Record<string, DetectionGtMetrics>;
  /** Phase 8 DET-STRETCH-02 — fused cross-robot detections */
  fusedDetections: FusedDetection[];

  // Setters
  updateMetrics: (robotId: string, metrics: SlamMetrics) => void;
  updateAllMetrics: (
    slam_metrics: Record<string, SlamMetrics>,
    baseline: Record<string, SlamMetrics> | null,
    history: Record<string, MetricHistory>,
    detection_metrics: Record<string, DetectionMetrics>,
    detection_history: Record<string, DetectionMetricHistory>,
    detection_gt_metrics: Record<string, DetectionGtMetrics>,
  ) => void;
  setBaseline: (baseline: Record<string, SlamMetrics> | null) => void;
  setViewMode: (mode: 'live' | 'baseline') => void;
  setOutputMode: (mode: 'cloud' | 'voxel' | 'mesh') => void;
  setOutputHidden: (hidden: boolean) => void;
  updateHistory: (robotId: string, history: MetricHistory) => void;
  setFusedDetections: (detections: FusedDetection[]) => void;
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
    const stored = localStorage.getItem('argus-outputMode');
    return stored === 'cloud' || stored === 'voxel' || stored === 'mesh' ? stored : 'cloud';
  })(),
  outputHidden: localStorage.getItem('argus-outputHidden') === 'true',
  history: {},
  meshVertices: null,
  meshFaces: null,
  meshColors: null,
  detectionPerRobot: {},
  detectionHistory: {},
  detectionGtPerRobot: {},
  fusedDetections: [],

  updateMetrics: (robotId, metrics) =>
    set((state) => ({
      perRobot: { ...state.perRobot, [robotId]: metrics },
    })),

  // Phase v2.0 13-01 invariant: ONE set() call covers all stats fields
  // to preserve the one-re-render-per-stats-message guarantee. Do NOT
  // split into multiple setters (Phase 6 DET-METRICS-01 — 6-arg revision
  // 2026-04-15 adds detection_metrics + detection_history + detection_gt_metrics).
  updateAllMetrics: (slam_metrics, baseline, history, detection_metrics, detection_history, detection_gt_metrics) =>
    set({
      perRobot: slam_metrics,
      baseline: baseline,
      history,
      detectionPerRobot: detection_metrics,
      detectionHistory: detection_history,
      detectionGtPerRobot: detection_gt_metrics,
    }),

  setBaseline: (baseline) => set({ baseline }),
  setViewMode: (mode) => set({ viewMode: mode }),
  setOutputMode: (mode) => {
    localStorage.setItem('argus-outputMode', mode);
    set({ outputMode: mode });
  },
  setOutputHidden: (hidden) => {
    localStorage.setItem('argus-outputHidden', String(hidden));
    set({ outputHidden: hidden });
  },
  updateHistory: (robotId, history) =>
    set((state) => ({
      history: { ...state.history, [robotId]: history },
    })),
  setFusedDetections: (detections) => set({ fusedDetections: detections }),
  setMeshData: (vertices, faces, colors = null) =>
    set({ meshVertices: vertices, meshFaces: faces, meshColors: colors }),
  clearMeshData: () =>
    set({ meshVertices: null, meshFaces: null, meshColors: null }),
}));
