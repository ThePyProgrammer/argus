/**
 * Plan 07-07 target — DET-PIPELINE-01 node catalog.
 *
 * Asserts NODE_DEFINITIONS contains the three perception entries
 * (detector_generic, detection3d_generic, tracker_generic) with the
 * port sets locked by CONTEXT D-03, D-04, D-05, and viz_output gains
 * tracks_in per D-06.
 */
import { describe, it, expect } from 'vitest';

describe.skip('NODE_DEFINITIONS perception entries (Plan 07-07)', () => {
  it('defines detector_generic with image_in + depth_in inputs and 2D/3D outputs', () => {
    // TODO Plan 07-07: import NODE_DEFINITIONS; assert detector_generic.inputs
    // has {id:'image_in', dataType:'Image', required:true} + {id:'depth_in',
    // dataType:'Image', required:false}; outputs has detections_2d_out
    // (Detections2D) + detections_3d_out (Detections3D).
    expect(false).toBe(true);
  });

  it('defines detection3d_generic with detections_2d_in + depth_in + optional pose_in', () => {
    // TODO Plan 07-07: per CONTEXT D-04.
    expect(false).toBe(true);
  });

  it('defines tracker_generic with detections_3d_in input and tracks_out output', () => {
    // TODO Plan 07-07: per CONTEXT D-05.
    expect(false).toBe(true);
  });

  it('extends viz_output with optional tracks_in port', () => {
    // TODO Plan 07-07: NODE_DEFINITIONS.viz_output.inputs contains
    // {id:'tracks_in', dataType:'Tracks', required:false} per CONTEXT D-06.
    expect(false).toBe(true);
  });

  it('assigns perception category to all three new node defs', () => {
    // TODO Plan 07-07: detector_generic.category === 'perception' (same for others).
    expect(false).toBe(true);
  });
});
