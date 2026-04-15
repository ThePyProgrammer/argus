/**
 * Plan 07-12 target — D-02 NodeInspector backend-dropdown hot-swap UI flow.
 *
 * D-02 (CONTEXT.md): "Users change the active backend by editing the node’s
 * `backend` param in the Inspector (a dropdown sourced from DetectorRegistry.list())
 * — NOT by deleting and replacing the node. registryName on the node data is
 * mutable; updateNodeParam on key 'backend' updates data.registryName + the
 * parameterSchema (refetched from /api/pipeline/node-catalog)."
 *
 * SC#4 end-to-end is exercisable from the Inspector — not just integration tests.
 *
 * Locked behaviors this stub will assert in Plan 07-12:
 *   1. NodeInspector renders a backend <select> dropdown when nodeType starts with
 *      `detector_`, `detection3d_`, or `tracker_`.
 *   2. Dropdown options come from pipelineStore.availableRegistryNodes filtered by
 *      category === 'perception' AND base node-kind matching the selected node’s
 *      nodeType prefix (detector_* shows only detector_* registry entries, etc.).
 *   3. Changing the dropdown calls updateNodeParam(nodeId, 'backend', newRegistryName).
 *   4. After updateNodeParam fires with key === 'backend', the selected node’s
 *      data.registryName mutates AND parameterSchema is refetched from
 *      /api/pipeline/node-catalog (parameterSchema replaced + paramValues reset to
 *      the new backend’s defaultParams).
 *   5. The non-perception case (sensor / slam / merger / filter / output): NO
 *      backend dropdown is rendered (regression guard — we don’t want a
 *      dropdown on non-hot-swappable nodes).
 */
import { describe, it, expect } from 'vitest';

describe.skip('NodeInspector backend dropdown — D-02 hot-swap (Plan 07-12)', () => {
  it('renders a <select> dropdown for detector_generic nodes', () => {
    // TODO Plan 07-12: render NodeInspector with a selected detector_generic node
    // (registryName: "yolov11"); query the dropdown by role 'combobox' or
    // accessible name "Backend"; assert it exists.
    expect(false).toBe(true);
  });

  it('renders a <select> dropdown for detection3d_generic nodes', () => {
    // TODO Plan 07-12: same as above, registryName: "point_cluster".
    expect(false).toBe(true);
  });

  it('renders a <select> dropdown for tracker_generic nodes', () => {
    // TODO Plan 07-12: same as above, registryName: "none".
    expect(false).toBe(true);
  });

  it('does NOT render a backend dropdown for non-perception nodes', () => {
    // TODO Plan 07-12: render NodeInspector with a slam_generic node;
    // assert no combobox / no "Backend" select rendered (only the static
    // "Backend: {registryName}" label from the existing inspector).
    expect(false).toBe(true);
  });

  it('options are sourced from pipelineStore.availableRegistryNodes filtered by node-kind prefix', () => {
    // TODO Plan 07-12: seed pipelineStore.setAvailableRegistryNodes([
    //   {type:'detector_yolov11', registryName:'yolov11', category:'perception', ...},
    //   {type:'detector_rtdetrv2', registryName:'rtdetrv2', category:'perception', ...},
    //   {type:'detection3d_point_cluster', registryName:'point_cluster', category:'perception', ...},
    //   {type:'tracker_none', registryName:'none', category:'perception', ...},
    // ]); render Inspector with a detector_generic node; assert the dropdown has
    // exactly 2 options (yolov11, rtdetrv2) — NOT detection3d_* or tracker_*.
    expect(false).toBe(true);
  });

  it('changing the dropdown calls updateNodeParam(nodeId, "backend", newRegistryName)', () => {
    // TODO Plan 07-12: spy on usePipelineStore.getState().updateNodeParam;
    // simulate user selecting a new option; assert spy called with
    // (selectedNodeId, 'backend', 'rtdetrv2').
    expect(false).toBe(true);
  });

  it('after backend change, data.registryName updates AND parameterSchema is refetched', () => {
    // TODO Plan 07-12: mock global.fetch for /api/pipeline/node-catalog returning
    // a parameterSchema for rtdetrv2; trigger dropdown change; await microtasks;
    // assert state.nodes[idx].data.registryName === 'rtdetrv2' AND
    // .parameterSchema deep-equals the catalog response for that backend AND
    // .paramValues has been reset to the new backend’s defaults.
    expect(false).toBe(true);
  });
});
