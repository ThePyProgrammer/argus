import { create } from 'zustand';
import type { SemanticMapObject } from '../utils/messageTypes';

interface SemanticMapStoreState {
  objects: Record<string, SemanticMapObject>;
  visible: boolean;
  currentSimTime: number;
  addOrUpdate: (objects: SemanticMapObject[]) => void;
  remove: (ids: number[]) => void;
  clear: () => void;
  setVisible: (visible: boolean) => void;
  setCurrentSimTime: (t: number) => void;
}

export const useSemanticMapStore = create<SemanticMapStoreState>((set) => ({
  objects: {},
  visible: true,
  currentSimTime: 0,
  addOrUpdate: (objects) =>
    set((state) => {
      const next = { ...state.objects };
      for (const obj of objects) {
        next[String(obj.fused_track_id)] = obj;
      }
      return { objects: next };
    }),
  remove: (ids) =>
    set((state) => {
      const next = { ...state.objects };
      for (const id of ids) {
        delete next[String(id)];
      }
      return { objects: next };
    }),
  clear: () => set({ objects: {} }),
  setVisible: (visible) => set({ visible }),
  setCurrentSimTime: (t) => set({ currentSimTime: t }),
}));
