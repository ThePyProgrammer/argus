import { create } from 'zustand';
import { applyNodeChanges, applyEdgeChanges, addEdge } from '@xyflow/react';
import type { OnNodesChange, OnEdgesChange, OnConnect, XYPosition } from '@xyflow/react';
import type {
  PipelineNode,
  PipelineEdge,
  PipelineNodeData,
  PresetInfo,
  ValidationError,
  PipelineConfig,
  PortDataType,
  RegistryNode,
} from '../utils/pipelineTypes';
import { buildNodeData, NODE_DEFINITIONS } from '../utils/nodeDefinitions';
import { validateGraph } from '../utils/pipelineValidation';
import { serializeGraph, deserializeGraph } from '../utils/pipelineSerializer';

interface PipelineStoreState {
  // Graph state
  nodes: PipelineNode[];
  edges: PipelineEdge[];
  selectedNodeId: string | null;

  // Preset state
  activePreset: string | null;
  availablePresets: PresetInfo[];
  isDirty: boolean;

  // Validation
  validationErrors: ValidationError[];
  isValid: boolean;

  // Pipeline status (from backend WS)
  isApplying: boolean;
  nodeStatuses: Record<string, string>;
  edgeThroughputs: Record<string, number>;

  // Last applied config for reset
  lastAppliedConfig: PipelineConfig | null;

  // Phase 7 D-02 — registry catalog entries (lifted from App.tsx local state)
  availableRegistryNodes: RegistryNode[];

  // React Flow callbacks
  onNodesChange: OnNodesChange;
  onEdgesChange: OnEdgesChange;
  onConnect: OnConnect;

  // Actions
  selectNode: (id: string | null) => void;
  addNode: (
    defKey: string,
    position: XYPosition,
    registryName?: string,
    registrySchema?: Record<string, unknown>,
  ) => void;
  removeNode: (id: string) => void;
  updateNodeParam: (nodeId: string, key: string, value: unknown) => void;
  validate: () => void;
  serializeForApply: () => PipelineConfig;
  markApplied: () => void;
  setNodeStatus: (nodeId: string, status: string) => void;
  setEdgeThroughput: (edgeId: string, fps: number) => void;
  setIsApplying: (applying: boolean) => void;
  setAvailablePresets: (presets: PresetInfo[]) => void;
  setAvailableRegistryNodes: (nodes: RegistryNode[]) => void;
  loadPresetGraph: (nodes: PipelineNode[], edges: PipelineEdge[], presetName: string) => void;
  resetToLastApplied: () => void;
}

export const usePipelineStore = create<PipelineStoreState>((set, get) => ({
  // Default state
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

  // React Flow callbacks
  onNodesChange: (changes) => {
    set((state) => ({
      nodes: applyNodeChanges(changes, state.nodes) as PipelineNode[],
      isDirty: true,
    }));
  },

  onEdgesChange: (changes) => {
    set((state) => ({
      edges: applyEdgeChanges(changes, state.edges) as PipelineEdge[],
      isDirty: true,
    }));
  },

  onConnect: (connection) => {
    set((state) => {
      // Phase 7 DET-PIPELINE-03 D-08 — resolve edge dataType from source output port
      // (fixes former hardcoded 'PointCloud' bug).
      const sourceNode = state.nodes.find((n) => n.id === connection.source);
      const sourcePort = sourceNode?.data.outputs.find(
        (p) => p.id === connection.sourceHandle,
      );
      const dataType: PortDataType = sourcePort?.dataType ?? 'PointCloud';
      return {
        edges: addEdge(
          {
            ...connection,
            type: 'animated',
            data: { fps: 0, dataType },
          },
          state.edges,
        ) as PipelineEdge[],
        isDirty: true,
      };
    });
  },

  selectNode: (id) => set({ selectedNodeId: id }),

  addNode: (defKey, position, registryName, registrySchema) => {
    const data = buildNodeData(defKey, registryName, registrySchema);
    const newNode: PipelineNode = {
      id: `${defKey}_${Date.now()}`,
      type: 'pipeline',
      position,
      data,
    };
    set((state) => ({
      nodes: [...state.nodes, newNode],
      isDirty: true,
    }));
  },

  removeNode: (id) => {
    set((state) => ({
      nodes: state.nodes.filter((n) => n.id !== id),
      edges: state.edges.filter((e) => e.source !== id && e.target !== id),
      selectedNodeId: state.selectedNodeId === id ? null : state.selectedNodeId,
      isDirty: true,
    }));
  },

  updateNodeParam: (nodeId, key, value) => {
    set((state) => {
      // Phase 7 D-02 hot-swap: changing 'backend' on a perception node mutates
      // registryName + replaces parameterSchema + resets paramValues to the new
      // schema's defaults. For all other keys, fall through to the legacy
      // paramValues[key] = value path.
      if (key === 'backend') {
        const newRegistryName = String(value);
        return {
          nodes: state.nodes.map((node) => {
            if (node.id !== nodeId) return node;
            // Resolve base node-kind: 'detector_generic' -> 'detector', etc.
            const nodeType = node.data.nodeType ?? '';
            const baseKind = nodeType.replace(/_generic$/, '');
            const expectedRegistryType = `${baseKind}_${newRegistryName}`;
            const match = state.availableRegistryNodes.find(
              (rn) => rn.type === expectedRegistryType,
            );
            if (!match) {
              // Defensive fallback: catalog not populated; legacy paramValues write.
              return {
                ...node,
                data: {
                  ...node.data,
                  paramValues: { ...node.data.paramValues, [key]: value },
                },
              };
            }
            // Reset paramValues to the new schema's defaults.
            const newDefaults: Record<string, unknown> = {};
            const props = (match.parameterSchema?.properties ?? {}) as Record<
              string,
              Record<string, unknown>
            >;
            for (const [pkey, prop] of Object.entries(props)) {
              if ('default' in prop) newDefaults[pkey] = prop.default;
            }
            return {
              ...node,
              data: {
                ...node.data,
                registryName: newRegistryName,
                parameterSchema: match.parameterSchema
                  ? { ...match.parameterSchema }
                  : null,
                paramValues: newDefaults,
              },
            };
          }),
          isDirty: true,
        };
      }
      // Default path (unchanged from pre-revision).
      return {
        nodes: state.nodes.map((node) =>
          node.id === nodeId
            ? {
                ...node,
                data: {
                  ...node.data,
                  paramValues: { ...node.data.paramValues, [key]: value },
                },
              }
            : node,
        ),
        isDirty: true,
      };
    });
  },

  validate: () => {
    const { nodes, edges } = get();
    const errors = validateGraph(nodes, edges);
    set({ validationErrors: errors, isValid: errors.length === 0 });
  },

  serializeForApply: () => {
    const { nodes, edges } = get();
    return serializeGraph(nodes, edges);
  },

  markApplied: () => {
    const { nodes, edges } = get();
    set({
      isDirty: false,
      lastAppliedConfig: serializeGraph(nodes, edges),
    });
  },

  setNodeStatus: (nodeId, status) => {
    set((state) => ({
      nodeStatuses: { ...state.nodeStatuses, [nodeId]: status },
      nodes: state.nodes.map((n) =>
        n.id === nodeId
          ? { ...n, data: { ...n.data, status: status as PipelineNodeData['status'] } }
          : n,
      ),
    }));
  },

  setEdgeThroughput: (edgeId, fps) => {
    set((state) => ({
      edgeThroughputs: { ...state.edgeThroughputs, [edgeId]: fps },
      edges: state.edges.map((e) =>
        e.id === edgeId && e.data
          ? { ...e, data: { dataType: e.data.dataType, fps } }
          : e,
      ),
    }));
  },

  setIsApplying: (applying) => set({ isApplying: applying }),

  setAvailablePresets: (presets) => set({ availablePresets: presets }),

  setAvailableRegistryNodes: (nodes) => set({ availableRegistryNodes: nodes }),

  loadPresetGraph: (nodes, edges, presetName) => {
    set({
      nodes,
      edges,
      activePreset: presetName,
      isDirty: false,
      selectedNodeId: null,
    });
  },

  resetToLastApplied: () => {
    const { lastAppliedConfig } = get();
    if (!lastAppliedConfig) return;
    const { nodes, edges } = deserializeGraph(lastAppliedConfig, NODE_DEFINITIONS);
    set({
      nodes,
      edges,
      isDirty: false,
      selectedNodeId: null,
    });
  },
}));
