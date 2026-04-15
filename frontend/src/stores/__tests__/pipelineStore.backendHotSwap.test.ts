/**
 * Plan 07-12 Task 1 — pipelineStore availableRegistryNodes + updateNodeParam('backend') hot-swap.
 *
 * D-02 (CONTEXT.md): setting key === 'backend' on a perception node must mutate
 * data.registryName + replace data.parameterSchema + reset data.paramValues to
 * the new backend's defaults (extracted from schema.properties[k].default).
 * Non-'backend' keys retain the legacy paramValues[key] = value path.
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { usePipelineStore } from '../pipelineStore';
import type { RegistryNode } from '../../utils/pipelineTypes';

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

describe('pipelineStore — availableRegistryNodes (Plan 07-12 Task 1)', () => {
  beforeEach(() => resetStore());

  it('exposes an empty availableRegistryNodes array by default', () => {
    expect(usePipelineStore.getState().availableRegistryNodes).toEqual([]);
  });

  it('setAvailableRegistryNodes writes the catalog list into the store', () => {
    usePipelineStore.getState().setAvailableRegistryNodes(REGISTRY_FIXTURE);
    expect(usePipelineStore.getState().availableRegistryNodes).toEqual(REGISTRY_FIXTURE);
  });
});

describe('pipelineStore.updateNodeParam("backend", ...) hot-swap branch (Plan 07-12 Task 1)', () => {
  beforeEach(() => resetStore());

  it('mutates registryName + replaces parameterSchema + resets paramValues to new defaults', () => {
    const s = usePipelineStore.getState();
    s.addNode('detector_generic', { x: 0, y: 0 }, 'yolov11');
    const nodeId = usePipelineStore.getState().nodes[0].id;
    usePipelineStore.getState().setAvailableRegistryNodes(REGISTRY_FIXTURE);

    usePipelineStore.getState().updateNodeParam(nodeId, 'backend', 'rtdetrv2');

    const updated = usePipelineStore.getState().nodes.find((n) => n.id === nodeId)!;
    expect(updated.data.registryName).toBe('rtdetrv2');
    expect(updated.data.parameterSchema).toEqual({
      properties: { conf_thresh: { type: 'number', default: 0.4 } },
    });
    expect(updated.data.paramValues).toEqual({ conf_thresh: 0.4 });
  });

  it('falls back to legacy paramValues write when no matching registry entry is found', () => {
    const s = usePipelineStore.getState();
    s.addNode('detector_generic', { x: 0, y: 0 }, 'yolov11');
    const nodeId = usePipelineStore.getState().nodes[0].id;
    // NOTE: no setAvailableRegistryNodes — catalog empty, fallback path.

    usePipelineStore.getState().updateNodeParam(nodeId, 'backend', 'nonexistent_backend');

    const updated = usePipelineStore.getState().nodes.find((n) => n.id === nodeId)!;
    // Fallback: paramValues['backend'] written; registryName untouched.
    expect(updated.data.registryName).toBe('yolov11');
    expect(updated.data.paramValues.backend).toBe('nonexistent_backend');
  });

  it('preserves legacy behavior for non-"backend" keys', () => {
    const s = usePipelineStore.getState();
    s.addNode('detector_generic', { x: 0, y: 0 }, 'yolov11');
    const nodeId = usePipelineStore.getState().nodes[0].id;
    usePipelineStore.getState().setAvailableRegistryNodes(REGISTRY_FIXTURE);

    usePipelineStore.getState().updateNodeParam(nodeId, 'conf_thresh', 0.75);

    const updated = usePipelineStore.getState().nodes.find((n) => n.id === nodeId)!;
    expect(updated.data.registryName).toBe('yolov11'); // untouched
    expect(updated.data.paramValues.conf_thresh).toBe(0.75);
  });
});
