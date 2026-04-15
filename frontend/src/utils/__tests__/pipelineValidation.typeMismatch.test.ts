/**
 * Plan 07-06 — DET-PIPELINE-03 SC#2 per-edge type validation lockdown.
 *
 * Depends on Plan 07-07 running in the same wave to populate
 * NODE_DEFINITIONS with `detector_generic` and `tracker_generic`. The
 * wave-2 gate runs typecheck + vitest after BOTH plans land; standalone
 * sampling of Plan 07-06 before 07-07 will surface expected failures.
 */
import { describe, it, expect } from 'vitest';
import type { PipelineNode, PipelineEdge } from '../pipelineTypes';
import { findPortTypeMismatches, validateGraph } from '../pipelineValidation';
import { buildNodeData } from '../nodeDefinitions';

function mkNode(id: string, defKey: string): PipelineNode {
  return {
    id,
    type: 'pipeline',
    position: { x: 0, y: 0 },
    data: buildNodeData(defKey),
  };
}

function mkEdge(
  id: string,
  source: string,
  sourceHandle: string,
  target: string,
  targetHandle: string,
): PipelineEdge {
  return {
    id,
    source,
    sourceHandle,
    target,
    targetHandle,
    type: 'animated',
    data: { fps: 0, dataType: 'PointCloud' },
  };
}

describe('findPortTypeMismatches (Plan 07-06)', () => {
  it('returns empty array when all edges have matching port types', () => {
    const nodes: PipelineNode[] = [mkNode('s', 'sensor_rgbd'), mkNode('d', 'slam_generic')];
    const edges: PipelineEdge[] = [mkEdge('e1', 's', 'image_out', 'd', 'image_in')]; // Image → Image
    expect(findPortTypeMismatches(nodes, edges)).toEqual([]);
  });

  it('returns ValidationError when PointCloud connects to Image', () => {
    const nodes: PipelineNode[] = [mkNode('slam', 'slam_generic'), mkNode('det', 'detector_generic')];
    const edges: PipelineEdge[] = [mkEdge('e1', 'slam', 'cloud_out', 'det', 'image_in')];
    const errors = findPortTypeMismatches(nodes, edges);
    expect(errors).toHaveLength(1);
    expect(errors[0].message).toMatch(/has mismatched types/);
    expect(errors[0].message).toContain('PointCloud');
    expect(errors[0].message).toContain('Image');
  });

  it('returns ValidationError when Detections2D connects to Detections3D input', () => {
    const nodes: PipelineNode[] = [mkNode('det', 'detector_generic'), mkNode('trk', 'tracker_generic')];
    const edges: PipelineEdge[] = [mkEdge('e1', 'det', 'detections_2d_out', 'trk', 'detections_3d_in')];
    const errors = findPortTypeMismatches(nodes, edges);
    expect(errors).toHaveLength(1);
    expect(errors[0].message).toContain('Detections2D');
    expect(errors[0].message).toContain('Detections3D');
  });

  it('emits mismatch error in CONTEXT D-09 literal format', () => {
    const slam = mkNode('slam', 'slam_generic');
    const det = mkNode('det', 'detector_generic');
    const mismatchingEdges: PipelineEdge[] = [mkEdge('e1', 'slam', 'cloud_out', 'det', 'image_in')];
    const errors = findPortTypeMismatches([slam, det], mismatchingEdges);
    expect(errors).toHaveLength(1);
    const srcPort = slam.data.outputs.find((p) => p.id === 'cloud_out')!;
    const tgtPort = det.data.inputs.find((p) => p.id === 'image_in')!;
    const expected =
      `Edge from ${slam.data.label}.${srcPort.label} (${srcPort.dataType}) ` +
      `to ${det.data.label}.${tgtPort.label} (${tgtPort.dataType}) ` +
      `has mismatched types`;
    expect(errors[0].message).toBe(expected);
  });

  it('validateGraph hooks findPortTypeMismatches BEFORE findUnconnectedPorts', () => {
    // Graph with BOTH a type mismatch AND an unconnected required input.
    // Type error must appear first in the errors array.
    const nodes: PipelineNode[] = [
      mkNode('slam', 'slam_generic'),
      mkNode('det', 'detector_generic'),
      mkNode('viz', 'viz_output'),
    ];
    const edges: PipelineEdge[] = [
      mkEdge('e1', 'slam', 'cloud_out', 'det', 'image_in'), // type mismatch PointCloud → Image
    ];
    const errors = validateGraph(nodes, edges);
    const mismatchIdx = errors.findIndex((e) => e.message.includes('has mismatched types'));
    const unconnectedIdx = errors.findIndex((e) => e.message.includes('unconnected required input'));
    expect(mismatchIdx).toBeGreaterThanOrEqual(0);
    expect(unconnectedIdx).toBeGreaterThanOrEqual(0);
    expect(mismatchIdx).toBeLessThan(unconnectedIdx);
  });
});
