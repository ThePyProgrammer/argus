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
    set((state) => ({
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
    }));
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
