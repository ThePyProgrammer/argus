import { create } from 'zustand';

export interface DetectorBackend {
  name: string;
  display: string;
  available: boolean;
  capabilities: Record<string, string | number | boolean>;
  parameter_schema: {
    type: string;
    properties: Record<
      string,
      {
        type: string;
        default?: number | boolean | string;
        minimum?: number;
        maximum?: number;
        description?: string;
        live_tunable?: boolean;
      }
    >;
  };
  reason?: string;
}

export interface LifterBackend {
  name: string;
  display: string;
  available: boolean;
  capabilities: Record<string, string | number | boolean>;
  parameter_schema: DetectorBackend['parameter_schema'];
  reason?: string;
}

interface DetectorStoreState {
  // --- Detector state (mirror slamStore) ---
  backends: DetectorBackend[];
  activeBackend: string;
  activeDisplay: string;
  activeParameters: Record<string, unknown>;
  stagedParams: Record<string, unknown>;
  isRestarting: boolean;
  error: string | null;
  crashMessage: string | null;

  // --- Lifter state (D-02 additions) ---
  lifters: LifterBackend[];
  activeLifter: string;
  activeLifterDisplay: string;
  activeLifterParameters: Record<string, unknown>;
  stagedLifterParams: Record<string, unknown>;

  // --- D-12 stacked overlay discriminator (Plan 10 extension) ---
  // Tracks which subsystem the current restart is for so SceneViewer can
  // render the correct RestartOverlay (detector vs lifter).
  restartSubsystem: 'detector' | 'lifter' | null;

  // --- Detector setters (mirror slamStore) ---
  setBackends: (backends: DetectorBackend[]) => void;
  setActive: (name: string, display: string, parameters: Record<string, unknown>) => void;
  setRestarting: (restarting: boolean) => void;
  stageParam: (key: string, value: unknown) => void;
  clearStagedParams: () => void;
  setError: (error: string | null) => void;
  updateActiveParam: (key: string, value: unknown) => void;
  setCrashMessage: (msg: string | null) => void;
  clearCrashMessage: () => void;

  // --- Lifter setters (D-02 additions) ---
  setLifters: (lifters: LifterBackend[]) => void;
  setActiveLifter: (name: string, display: string, parameters: Record<string, unknown>) => void;
  stageLifterParam: (key: string, value: unknown) => void;
  clearStagedLifterParams: () => void;
  updateActiveLifterParam: (key: string, value: unknown) => void;

  // --- D-12 stacked overlay discriminator setter (Plan 10 extension) ---
  setRestartSubsystem: (subsystem: 'detector' | 'lifter' | null) => void;
}

export const useDetectorStore = create<DetectorStoreState>((set) => ({
  // Detector defaults (mirror server.py:62 app.state default)
  backends: [],
  activeBackend: 'yolov11',
  activeDisplay: 'YOLOv11-nano',
  activeParameters: {},
  stagedParams: {},
  isRestarting: false,
  error: null,
  crashMessage: null,

  // Lifter defaults (D-02 + main.py restart block fallback;
  // mirror Detection3DRegistry.get_default() / MedianDepthLifter registration)
  lifters: [],
  activeLifter: 'median_depth',
  activeLifterDisplay: 'Median Depth (legacy)',
  activeLifterParameters: {},
  stagedLifterParams: {},

  // D-12 stacked overlay discriminator default
  restartSubsystem: null,

  // Detector setters
  setBackends: (backends: DetectorBackend[]) => set({ backends }),
  setActive: (name: string, display: string, parameters: Record<string, unknown>) =>
    set({ activeBackend: name, activeDisplay: display, activeParameters: parameters }),
  setRestarting: (restarting: boolean) => set({ isRestarting: restarting }),
  stageParam: (key: string, value: unknown) =>
    set((s) => ({ stagedParams: { ...s.stagedParams, [key]: value } })),
  clearStagedParams: () => set({ stagedParams: {} }),
  setError: (error: string | null) => set({ error }),
  updateActiveParam: (key: string, value: unknown) =>
    set((s) => ({ activeParameters: { ...s.activeParameters, [key]: value } })),
  setCrashMessage: (msg: string | null) => set({ crashMessage: msg }),
  clearCrashMessage: () => set({ crashMessage: null }),

  // Lifter setters (D-02 additions)
  setLifters: (lifters: LifterBackend[]) => set({ lifters }),
  setActiveLifter: (name: string, display: string, parameters: Record<string, unknown>) =>
    set({
      activeLifter: name,
      activeLifterDisplay: display,
      activeLifterParameters: parameters,
    }),
  stageLifterParam: (key: string, value: unknown) =>
    set((s) => ({ stagedLifterParams: { ...s.stagedLifterParams, [key]: value } })),
  clearStagedLifterParams: () => set({ stagedLifterParams: {} }),
  updateActiveLifterParam: (key: string, value: unknown) =>
    set((s) => ({
      activeLifterParameters: { ...s.activeLifterParameters, [key]: value },
    })),

  // D-12 stacked overlay discriminator setter (Plan 10 extension)
  setRestartSubsystem: (subsystem) => set({ restartSubsystem: subsystem }),
}));

export async function fetchDetectorState(): Promise<void> {
  const store = useDetectorStore.getState();
  try {
    const [backendsRes, activeRes, liftersRes, activeLifterRes] = await Promise.all([
      fetch('/api/detectors/backends'),
      fetch('/api/detectors/active'),
      fetch('/api/detectors/lifters'),
      fetch('/api/detectors/active-lifter'),
    ]);
    if (backendsRes.ok) {
      const data = await backendsRes.json();
      store.setBackends(data.backends);
    }
    if (activeRes.ok) {
      const data = await activeRes.json();
      store.setActive(data.backend, data.display, data.parameters);
    }
    if (liftersRes.ok) {
      const data = await liftersRes.json();
      store.setLifters(data.lifters);
    }
    if (activeLifterRes.ok) {
      const data = await activeLifterRes.json();
      store.setActiveLifter(data.lifter, data.display, data.parameters);
    }
  } catch {
    store.setError('Failed to load detector backends. Check that the server is running.');
  }
}
