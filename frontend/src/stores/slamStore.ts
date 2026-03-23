import { create } from 'zustand';

export interface SLAMBackend {
  name: string;
  display: string;
  available: boolean;
  capabilities: Record<string, boolean>;
  parameter_schema: {
    type: string;
    properties: Record<
      string,
      {
        type: string;
        default?: number | boolean;
        minimum?: number;
        maximum?: number;
        description?: string;
        live_tunable?: boolean;
      }
    >;
  };
  reason?: string;
}

interface SlamStoreState {
  backends: SLAMBackend[];
  activeBackend: string;
  activeDisplay: string;
  activeParameters: Record<string, unknown>;
  stagedParams: Record<string, unknown>;
  isRestarting: boolean;
  error: string | null;
  crashMessage: string | null;

  setBackends: (backends: SLAMBackend[]) => void;
  setActive: (name: string, display: string, parameters: Record<string, unknown>) => void;
  setRestarting: (restarting: boolean) => void;
  stageParam: (key: string, value: unknown) => void;
  clearStagedParams: () => void;
  setError: (error: string | null) => void;
  updateActiveParam: (key: string, value: unknown) => void;
  setCrashMessage: (msg: string | null) => void;
  clearCrashMessage: () => void;
}

export const useSlamStore = create<SlamStoreState>((set) => ({
  backends: [],
  activeBackend: 'icp',
  activeDisplay: 'ICP Odometry',
  activeParameters: {},
  stagedParams: {},
  isRestarting: false,
  error: null,
  crashMessage: null,

  setBackends: (backends: SLAMBackend[]) => set({ backends }),
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
}));

export async function fetchSlamState(): Promise<void> {
  const store = useSlamStore.getState();
  try {
    const [backendsRes, activeRes] = await Promise.all([
      fetch('/api/slam/backends'),
      fetch('/api/slam/active'),
    ]);
    if (backendsRes.ok) {
      const data = await backendsRes.json();
      store.setBackends(data.backends);
    }
    if (activeRes.ok) {
      const data = await activeRes.json();
      store.setActive(data.backend, data.display, data.parameters);
    }
  } catch {
    store.setError('Failed to load SLAM backends. Check that the server is running.');
  }
}
