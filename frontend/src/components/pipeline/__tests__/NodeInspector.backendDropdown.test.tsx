/**
 * Plan 07-12 — D-02 NodeInspector backend-dropdown hot-swap UI lockdown.
 *
 * Promoted from the Plan 07-02 skip-stub. Tests render NodeInspector against
 * a primed pipelineStore (selected node + availableRegistryNodes) and assert
 * the dropdown render conditions, options filtering, and store-mutation
 * side-effects (registryName + parameterSchema + paramValues).
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { usePipelineStore } from '../../../stores/pipelineStore';
import { NodeInspector } from '../NodeInspector';
import type { RegistryNode } from '../../../utils/pipelineTypes';

const REGISTRY_FIXTURE: RegistryNode[] = [
  {
    type: 'detector_yolov11',
    label: 'Detector: YOLOv11',
    category: 'perception',
    registryName: 'yolov11',
    parameterSchema: { properties: { conf_thresh: { type: 'number', default: 0.25 } } },
  },
  {
    type: 'detector_rtdetrv2',
    label: 'Detector: RT-DETRv2',
    category: 'perception',
    registryName: 'rtdetrv2',
    parameterSchema: { properties: { conf_thresh: { type: 'number', default: 0.4 } } },
  },
  {
    type: 'detection3d_point_cluster',
    label: '3D Lifter: PointCluster',
    category: 'perception',
    registryName: 'point_cluster',
    parameterSchema: { properties: {} },
  },
  {
    type: 'tracker_none',
    label: 'Tracker: Passthrough (no tracking)',
    category: 'perception',
    registryName: 'none',
    parameterSchema: null,
  },
];

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
    availableRegistryNodes: [],
  });
}

function seedDetectorNode(): string {
  const s = usePipelineStore.getState();
  s.addNode('detector_generic', { x: 0, y: 0 }, 'yolov11');
  const node = usePipelineStore.getState().nodes[0];
  usePipelineStore.getState().selectNode(node.id);
  usePipelineStore.getState().setAvailableRegistryNodes(REGISTRY_FIXTURE);
  return node.id;
}

describe('NodeInspector backend dropdown — D-02 hot-swap (Plan 07-12)', () => {
  beforeEach(() => resetStore());

  it('renders a <select> dropdown for detector_generic nodes', () => {
    seedDetectorNode();
    render(<NodeInspector />);
    expect(screen.getByLabelText('Backend')).toBeTruthy();
  });

  it('renders a <select> dropdown for detection3d_generic nodes', () => {
    const s = usePipelineStore.getState();
    s.addNode('detection3d_generic', { x: 0, y: 0 }, 'point_cluster');
    const node = usePipelineStore.getState().nodes[0];
    usePipelineStore.getState().selectNode(node.id);
    usePipelineStore.getState().setAvailableRegistryNodes(REGISTRY_FIXTURE);
    render(<NodeInspector />);
    expect(screen.getByLabelText('Backend')).toBeTruthy();
  });

  it('renders a <select> dropdown for tracker_generic nodes', () => {
    const s = usePipelineStore.getState();
    s.addNode('tracker_generic', { x: 0, y: 0 }, 'none');
    const node = usePipelineStore.getState().nodes[0];
    usePipelineStore.getState().selectNode(node.id);
    usePipelineStore.getState().setAvailableRegistryNodes(REGISTRY_FIXTURE);
    render(<NodeInspector />);
    expect(screen.getByLabelText('Backend')).toBeTruthy();
  });

  it('does NOT render a backend dropdown for non-perception nodes', () => {
    const s = usePipelineStore.getState();
    s.addNode('slam_generic', { x: 0, y: 0 }, 'icp');
    const node = usePipelineStore.getState().nodes[0];
    usePipelineStore.getState().selectNode(node.id);
    usePipelineStore.getState().setAvailableRegistryNodes(REGISTRY_FIXTURE);
    render(<NodeInspector />);
    expect(screen.queryByLabelText('Backend')).toBeNull();
  });

  it('options are sourced from availableRegistryNodes filtered by node-kind prefix', () => {
    seedDetectorNode();
    render(<NodeInspector />);
    const select = screen.getByLabelText('Backend') as HTMLSelectElement;
    const optionValues = Array.from(select.options).map((o) => o.value);
    // Only detector_* registry entries should appear — NOT detection3d_* or tracker_*.
    expect(optionValues).toEqual(expect.arrayContaining(['yolov11', 'rtdetrv2']));
    expect(optionValues).not.toContain('point_cluster');
    expect(optionValues).not.toContain('none');
  });

  it('changing the dropdown calls updateNodeParam(nodeId, "backend", newRegistryName)', () => {
    const nodeId = seedDetectorNode();
    const spy = vi.spyOn(usePipelineStore.getState(), 'updateNodeParam');
    render(<NodeInspector />);
    const select = screen.getByLabelText('Backend') as HTMLSelectElement;
    fireEvent.change(select, { target: { value: 'rtdetrv2' } });
    expect(spy).toHaveBeenCalledWith(nodeId, 'backend', 'rtdetrv2');
    spy.mockRestore();
  });

  it('after backend change: data.registryName updates AND parameterSchema is replaced AND paramValues reset', () => {
    const nodeId = seedDetectorNode();
    render(<NodeInspector />);
    const select = screen.getByLabelText('Backend') as HTMLSelectElement;
    fireEvent.change(select, { target: { value: 'rtdetrv2' } });
    const updated = usePipelineStore.getState().nodes.find((n) => n.id === nodeId)!;
    expect(updated.data.registryName).toBe('rtdetrv2');
    expect(updated.data.parameterSchema).toEqual({
      properties: { conf_thresh: { type: 'number', default: 0.4 } },
    });
    // paramValues reset to the new schema's defaults (extracted from properties[k].default).
    expect(updated.data.paramValues).toEqual({ conf_thresh: 0.4 });
  });
});
