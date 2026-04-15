/**
 * Plan 07-08 target — DET-PIPELINE-03 SC#2 regression lockdown.
 *
 * `pipelineStore.ts:101` currently hardcodes `dataType: 'PointCloud'` on every
 * edge created via `onConnect`. This test verifies the fix: the edge's
 * `data.dataType` comes from the source node's output port's dataType.
 *
 * Also locks down the parallel bug in `pipelineSerializer.ts:112` — every edge
 * deserialized from a preset JSON must carry the correct dataType.
 *
 * Literal reproducer from CONTEXT.md §specifics:
 *   sensor_rgbd.image_out (Image) → slam_generic.image_in (Image)
 *   expects edge.data.dataType === 'Image' (NOT 'PointCloud').
 */
import { describe, it, expect } from 'vitest';

describe.skip('pipelineStore.onConnect — dataType inference (Plan 07-08)', () => {
  it('resolves edge dataType from source handle (Image → Image case)', () => {
    // TODO Plan 07-08: set up store with sensor_rgbd + slam_generic nodes,
    // call onConnect({ source: 'sensor_1', sourceHandle: 'image_out',
    //   target: 'slam_1', targetHandle: 'image_in' }),
    // assert state.edges[0].data.dataType === 'Image'.
    expect(false).toBe(true);
  });

  it('resolves edge dataType for PointCloud → PointCloud case (regression)', () => {
    // TODO Plan 07-08: slam_generic.cloud_out (PointCloud) → merger_generic.cloud_in;
    // assert edge.data.dataType === 'PointCloud'.
    expect(false).toBe(true);
  });

  it('resolves edge dataType for new Detections2D → Detections2D case', () => {
    // TODO Plan 07-08: detector_generic.detections_2d_out → detection3d_generic.detections_2d_in;
    // assert edge.data.dataType === 'Detections2D'.
    expect(false).toBe(true);
  });

  it('falls back to PointCloud defensively when source port cannot be resolved', () => {
    // TODO Plan 07-08: supply connection with unknown sourceHandle;
    // assert edge.data.dataType === 'PointCloud' (defensive fallback).
    expect(false).toBe(true);
  });
});

describe.skip('pipelineSerializer.deserializeGraph — edge dataType (Plan 07-08)', () => {
  it('resolves edge dataType from source handle on deserialize', () => {
    // TODO Plan 07-08: build a PipelineConfig with one edge from
    // detector_generic.detections_2d_out → detection3d_generic.detections_2d_in;
    // call deserializeGraph; assert edges[0].data.dataType === 'Detections2D'
    // (NOT 'PointCloud' — today's bug at pipelineSerializer.ts:112).
    expect(false).toBe(true);
  });
});
