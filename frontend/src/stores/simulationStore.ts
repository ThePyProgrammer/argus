import { create } from 'zustand';
import { useRobotStore } from './robotStore';
export interface SimulationStatus {
  phase: string;
  scene?: string;
  message: string;
  positions?: Record<string, [number, number, number]>;
  headings?: Record<string, number>;
}
export const useSimulationStore = create<{ status: SimulationStatus; apply: (status: SimulationStatus) => void }>((set, get) => ({
  status: { phase: 'idle', message: '' },
  apply: (status) => {
    const previous = get().status;
    set({ status });
    if (status.phase !== 'loading' || !status.positions) return;
    if (previous.phase === 'loading' && previous.scene === status.scene && JSON.stringify(previous.positions) === JSON.stringify(status.positions)) return;
    const store = useRobotStore.getState();
    store.setRobotList(Object.keys(status.positions));
    store.setCloudFull([], []);
    for (const [id, position] of Object.entries(status.positions)) {
      store.updatePose(id, position, [], 'initializing', status.headings?.[id] ?? 0);
      store.updateTrajectory(id, [], []);
      store.updateDetections(id, null);
    }
  },
}));
