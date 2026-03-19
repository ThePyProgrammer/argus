import { create } from 'zustand';

export interface ControlStoreState {
  isRunning: boolean;
  isPaused: boolean;
  simSpeed: number;
  sendCommand: ((cmd: { action: string; value?: number }) => void) | null;
  sendRaw: ((msg: Record<string, unknown>) => void) | null;

  // Cloud config
  cloudConfigs: Record<string, string>;
  activeCloudConfig: string;
  cloudOffset: [number, number, number]; // [x, y, z] offset applied to cloud in scene
  showScene: boolean; // toggle scene mesh visibility

  setRunning: (running: boolean) => void;
  setPaused: (paused: boolean) => void;
  setSimSpeed: (speed: number) => void;
  setSendCommand: (fn: (cmd: { action: string; value?: number }) => void) => void;
  setSendRaw: (fn: (msg: Record<string, unknown>) => void) => void;
  setCloudConfigs: (configs: Record<string, string>, active: string) => void;
  setActiveCloudConfig: (key: string) => void;
  setCloudOffset: (offset: [number, number, number]) => void;
  toggleScene: () => void;
}

export const useControlStore = create<ControlStoreState>((set) => ({
  isRunning: true,
  isPaused: false,
  simSpeed: 1.0,
  sendCommand: null,
  sendRaw: null,
  cloudConfigs: {},
  activeCloudConfig: 'G',
  cloudOffset: [0, 0, 0] as [number, number, number],
  showScene: true,

  setRunning: (running: boolean) => set({ isRunning: running }),
  setPaused: (paused: boolean) => set({ isPaused: paused }),
  setSimSpeed: (speed: number) => set({ simSpeed: speed }),
  setSendCommand: (fn) => set({ sendCommand: fn }),
  setSendRaw: (fn) => set({ sendRaw: fn }),
  setCloudConfigs: (configs, active) => set({ cloudConfigs: configs, activeCloudConfig: active }),
  setActiveCloudConfig: (key) => set({ activeCloudConfig: key }),
  setCloudOffset: (offset) => set({ cloudOffset: offset }),
  toggleScene: () => set((s) => ({ showScene: !s.showScene })),
}));
