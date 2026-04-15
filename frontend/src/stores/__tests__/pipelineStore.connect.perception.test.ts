/**
 * Plan 07-07 — DET-PIPELINE-01 SC#1 drag+connect integration.
 *
 * Note: the third dataType assertion in each test depends on Plan 08's
 * fix to pipelineStore.onConnect (currently hardcodes dataType: 'PointCloud').
 * Until Plan 08 lands, the dataType assertions will fail — that is an
 * intentional wave-gate coupling documented in 07-07-PLAN.md.
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { usePipelineStore } from '../../stores/pipelineStore';

function resetStore(): void {
  usePipelineStore.setState({
    nodes: [],
    edges: [],
    selectedNodeId: null,
    activePreset: null,
    availablePresets: [],
    isDirty: false,
    validationErrors: [],
    isValid: true,
    isApplying: false,
    nodeStatuses: {},
    edgeThroughputs: {},
    lastAppliedConfig: null,
  });
}

describe('Perception node drag+connect flow (Plan 07-07)', () => {
  beforeEach(() => resetStore());

  it('allows Detections2D → Detections2D connection without validation error', () => {
    const store = usePipelineStore.getState();
    store.addNode('detector_generic', { x: 100, y: 100 }, 'yolov11');
    store.addNode('detection3d_generic', { x: 300, y: 100 }, 'point_cluster');
    const { nodes: addedNodes } = usePipelineStore.getState();
    const detId = addedNodes[0].id;
    const d3dId = addedNodes[1].id;

    usePipelineStore.getState().onConnect({
      source: detId,
      sourceHandle: 'detections_2d_out',
      target: d3dId,
      targetHandle: 'detections_2d_in',
    });

    const { edges } = usePipelineStore.getState();
    expect(edges).toHaveLength(1);
    expect(edges[0].data?.dataType).toBe('Detections2D');
  });

  it('allows Detections3D → Detections3D connection without validation error', () => {
    const store = usePipelineStore.getState();
    store.addNode('detection3d_generic', { x: 100, y: 100 }, 'point_cluster');
    store.addNode('tracker_generic', { x: 300, y: 100 }, 'none');
    const { nodes: addedNodes } = usePipelineStore.getState();
    const d3dId = addedNodes[0].id;
    const trkId = addedNodes[1].id;

    usePipelineStore.getState().onConnect({
      source: d3dId,
      sourceHandle: 'detections_3d_out',
      target: trkId,
      targetHandle: 'detections_3d_in',
    });

    const { edges } = usePipelineStore.getState();
    expect(edges).toHaveLength(1);
    expect(edges[0].data?.dataType).toBe('Detections3D');
  });

  it('allows Tracks → Tracks connection to viz_output.tracks_in', () => {
    const store = usePipelineStore.getState();
    store.addNode('tracker_generic', { x: 100, y: 100 }, 'none');
    store.addNode('viz_output', { x: 300, y: 100 });
    const { nodes: addedNodes } = usePipelineStore.getState();
    const trkId = addedNodes[0].id;
    const vizId = addedNodes[1].id;

    usePipelineStore.getState().onConnect({
      source: trkId,
      sourceHandle: 'tracks_out',
      target: vizId,
      targetHandle: 'tracks_in',
    });

    const { edges } = usePipelineStore.getState();
    expect(edges).toHaveLength(1);
    expect(edges[0].data?.dataType).toBe('Tracks');
  });
});
