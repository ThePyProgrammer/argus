import { create } from 'zustand';

export interface ControlStoreState {
  isRunning: boolean;
  isPaused: boolean;
  simSpeed: number; // 0.1 to 5.0, default 1.0
  sendCommand: ((cmd: { action: string; value?: number }) => void) | null;

  setRunning: (running: boolean) => void;
  setPaused: (paused: boolean) => void;
  setSimSpeed: (speed: number) => void;
  setSendCommand: (
    fn: (cmd: { action: string; value?: number }) => void,
  ) => void;
}

export const useControlStore = create<ControlStoreState>((set) => ({
  isRunning: false,
  isPaused: false,
  simSpeed: 1.0,
  sendCommand: null,

  setRunning: (running: boolean) => set({ isRunning: running }),
  setPaused: (paused: boolean) => set({ isPaused: paused }),
  setSimSpeed: (speed: number) => set({ simSpeed: speed }),
  setSendCommand: (fn) => set({ sendCommand: fn }),
}));
