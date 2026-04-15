/**
 * Plan 07-07 — DET-PIPELINE-01 node catalog lockdown.
 */
import { describe, it, expect } from 'vitest';
import { NODE_DEFINITIONS } from '../nodeDefinitions';

describe('NODE_DEFINITIONS perception entries (Plan 07-07)', () => {
  it('defines detector_generic with image_in + depth_in inputs and 2D/3D outputs', () => {
    const def = NODE_DEFINITIONS.detector_generic;
    expect(def).toBeDefined();
    expect(def.category).toBe('perception');
    expect(def.inputs).toEqual([
      { id: 'image_in', label: 'Image', dataType: 'Image', required: true },
      { id: 'depth_in', label: 'Depth', dataType: 'Image', required: false },
    ]);
    expect(def.outputs).toEqual([
      { id: 'detections_2d_out', label: 'Detections 2D', dataType: 'Detections2D', required: false },
      { id: 'detections_3d_out', label: 'Detections 3D', dataType: 'Detections3D', required: false },
    ]);
  });

  it('defines detection3d_generic with detections_2d_in + depth_in + optional pose_in', () => {
    const def = NODE_DEFINITIONS.detection3d_generic;
    expect(def).toBeDefined();
    expect(def.category).toBe('perception');
    expect(def.inputs).toEqual([
      { id: 'detections_2d_in', label: 'Detections 2D', dataType: 'Detections2D', required: true },
      { id: 'depth_in', label: 'Depth', dataType: 'Image', required: true },
      { id: 'pose_in', label: 'Pose', dataType: 'Pose', required: false },
    ]);
    expect(def.outputs).toEqual([
      { id: 'detections_3d_out', label: 'Detections 3D', dataType: 'Detections3D', required: false },
    ]);
  });

  it('defines tracker_generic with detections_3d_in input and tracks_out output', () => {
    const def = NODE_DEFINITIONS.tracker_generic;
    expect(def).toBeDefined();
    expect(def.category).toBe('perception');
    expect(def.inputs).toEqual([
      { id: 'detections_3d_in', label: 'Detections 3D', dataType: 'Detections3D', required: true },
    ]);
    expect(def.outputs).toEqual([
      { id: 'tracks_out', label: 'Tracks', dataType: 'Tracks', required: false },
    ]);
  });

  it('extends viz_output with optional tracks_in port', () => {
    const viz = NODE_DEFINITIONS.viz_output;
    const tracksIn = viz.inputs.find((p) => p.id === 'tracks_in');
    expect(tracksIn).toBeDefined();
    expect(tracksIn).toEqual({ id: 'tracks_in', label: 'Tracks', dataType: 'Tracks', required: false });
  });

  it('assigns perception category to all three new node defs', () => {
    expect(NODE_DEFINITIONS.detector_generic.category).toBe('perception');
    expect(NODE_DEFINITIONS.detection3d_generic.category).toBe('perception');
    expect(NODE_DEFINITIONS.tracker_generic.category).toBe('perception');
  });
});
