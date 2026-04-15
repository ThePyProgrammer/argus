/**
 * Plan 07-08 — DET-PIPELINE-03 SC#2 dataType regression lockdown.
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { usePipelineStore } from '../../stores/pipelineStore';
import { deserializeGraph } from '../../utils/pipelineSerializer';
import { NODE_DEFINITIONS } from '../../utils/nodeDefinitions';

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

describe('pipelineStore.onConnect dataType resolution (Plan 07-08)', () => {
  beforeEach(() => resetStore());

  it('resolves edge dataType from source handle (Image → Image case)', () => {
    const s = usePipelineStore.getState();
    s.addNode('sensor_rgbd', { x: 0, y: 0 });
    s.addNode('slam_generic', { x: 100, y: 0 }, 'icp');
    const nodes = usePipelineStore.getState().nodes;
    usePipelineStore.getState().onConnect({
      source: nodes[0].id,
      sourceHandle: 'image_out',
      target: nodes[1].id,
      targetHandle: 'image_in',
    });
    const edges = usePipelineStore.getState().edges;
    expect(edges).toHaveLength(1);
    expect(edges[0].data?.dataType).toBe('Image');
  });

  it('resolves edge dataType for PointCloud → PointCloud case (regression)', () => {
    const s = usePipelineStore.getState();
    s.addNode('slam_generic', { x: 0, y: 0 }, 'icp');
    s.addNode('merger_generic', { x: 100, y: 0 }, 'icp_union');
    const nodes = usePipelineStore.getState().nodes;
    usePipelineStore.getState().onConnect({
      source: nodes[0].id,
      sourceHandle: 'cloud_out',
      target: nodes[1].id,
      targetHandle: 'cloud_in',
    });
    const edges = usePipelineStore.getState().edges;
    expect(edges[0].data?.dataType).toBe('PointCloud');
  });

  it('resolves edge dataType for new Detections2D → Detections2D case', () => {
    const s = usePipelineStore.getState();
    s.addNode('detector_generic', { x: 0, y: 0 }, 'yolov11');
    s.addNode('detection3d_generic', { x: 100, y: 0 }, 'point_cluster');
    const nodes = usePipelineStore.getState().nodes;
    usePipelineStore.getState().onConnect({
      source: nodes[0].id,
      sourceHandle: 'detections_2d_out',
      target: nodes[1].id,
      targetHandle: 'detections_2d_in',
    });
    const edges = usePipelineStore.getState().edges;
    expect(edges[0].data?.dataType).toBe('Detections2D');
  });

  it('falls back to PointCloud defensively when source port cannot be resolved', () => {
    const s = usePipelineStore.getState();
    s.addNode('sensor_rgbd', { x: 0, y: 0 });
    s.addNode('slam_generic', { x: 100, y: 0 }, 'icp');
    const nodes = usePipelineStore.getState().nodes;
    usePipelineStore.getState().onConnect({
      source: nodes[0].id,
      sourceHandle: 'nonexistent_handle',
      target: nodes[1].id,
      targetHandle: 'image_in',
    });
    const edges = usePipelineStore.getState().edges;
    expect(edges[0].data?.dataType).toBe('PointCloud');
  });
});

describe('pipelineSerializer.deserializeGraph edge dataType (Plan 07-08)', () => {
  it('resolves edge dataType from source handle on deserialize', () => {
    const config = {
      nodes: [
        { id: 'det_1', type: 'detector_yolov11', params: {}, position: { x: 0, y: 0 } },
        { id: 'd3d_1', type: 'detection3d_point_cluster', params: {}, position: { x: 100, y: 0 } },
      ],
      edges: [
        {
          source: 'det_1',
          sourceHandle: 'detections_2d_out',
          target: 'd3d_1',
          targetHandle: 'detections_2d_in',
        },
      ],
    };
    const { edges } = deserializeGraph(config, NODE_DEFINITIONS);
    expect(edges).toHaveLength(1);
    expect(edges[0].data?.dataType).toBe('Detections2D');
  });
});
