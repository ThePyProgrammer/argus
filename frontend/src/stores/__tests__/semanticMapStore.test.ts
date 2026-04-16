import { describe, test, expect, beforeEach } from 'vitest';
import { useSemanticMapStore } from '../semanticMapStore';
import type { SemanticMapObject } from '../../utils/messageTypes';

function makeObj(id: number, className: string = 'chair'): SemanticMapObject {
  return {
    fused_track_id: id,
    class_name: className,
    center: [1, 2, 3],
    half_extents: [0.5, 0.5, 0.5],
    quaternion: [0, 0, 0, 1],
    score: 0.9,
    last_seen: 10.0,
    ttl: 10.0,
  };
}

describe('semanticMapStore', () => {
  beforeEach(() => {
    // Reset store to initial state before each test
    useSemanticMapStore.setState({
      objects: {},
      visible: true,
      currentSimTime: 0,
    });
  });

  test('initial state has empty objects, visible: true, currentSimTime: 0', () => {
    const state = useSemanticMapStore.getState();
    expect(state.objects).toEqual({});
    expect(state.visible).toBe(true);
    expect(state.currentSimTime).toBe(0);
  });

  test('addOrUpdate inserts new objects keyed by fused_track_id', () => {
    const obj1 = makeObj(1, 'chair');
    const obj2 = makeObj(2, 'table');
    useSemanticMapStore.getState().addOrUpdate([obj1, obj2]);
    const state = useSemanticMapStore.getState();
    expect(Object.keys(state.objects)).toEqual(['1', '2']);
    expect(state.objects['1'].class_name).toBe('chair');
    expect(state.objects['2'].class_name).toBe('table');
  });

  test('addOrUpdate updates existing objects', () => {
    const obj = makeObj(1, 'chair');
    useSemanticMapStore.getState().addOrUpdate([obj]);
    const updated = { ...obj, score: 0.95, class_name: 'desk' };
    useSemanticMapStore.getState().addOrUpdate([updated]);
    const state = useSemanticMapStore.getState();
    expect(Object.keys(state.objects)).toEqual(['1']);
    expect(state.objects['1'].score).toBe(0.95);
    expect(state.objects['1'].class_name).toBe('desk');
  });

  test('remove deletes objects by fused_track_id', () => {
    useSemanticMapStore.getState().addOrUpdate([makeObj(1), makeObj(2), makeObj(3)]);
    useSemanticMapStore.getState().remove([1, 3]);
    const state = useSemanticMapStore.getState();
    expect(Object.keys(state.objects)).toEqual(['2']);
  });

  test('clear removes all objects', () => {
    useSemanticMapStore.getState().addOrUpdate([makeObj(1), makeObj(2)]);
    useSemanticMapStore.getState().clear();
    const state = useSemanticMapStore.getState();
    expect(state.objects).toEqual({});
  });

  test('setVisible toggles visible flag', () => {
    expect(useSemanticMapStore.getState().visible).toBe(true);
    useSemanticMapStore.getState().setVisible(false);
    expect(useSemanticMapStore.getState().visible).toBe(false);
    useSemanticMapStore.getState().setVisible(true);
    expect(useSemanticMapStore.getState().visible).toBe(true);
  });

  test('setCurrentSimTime updates currentSimTime', () => {
    useSemanticMapStore.getState().setCurrentSimTime(42.5);
    expect(useSemanticMapStore.getState().currentSimTime).toBe(42.5);
  });
});
