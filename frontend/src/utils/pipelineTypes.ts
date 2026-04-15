import type { Node, Edge } from '@xyflow/react';

// Port data types (per CONTEXT.md locked decision: typed ports with visual hints)
// Port data types (CONTEXT.md Phase 7 D-07 adds Detections2D/Detections3D/Tracks)
export type PortDataType =
  | 'Image'
  | 'PointCloud'
  | 'Pose'
  | 'IMU'
  | 'Scalar'
  | 'Boolean'
  | 'Config'
  | 'Detections2D'  // Phase 7 DET-PIPELINE-02 (coral #ff8a65)
  | 'Detections3D'  // Phase 7 DET-PIPELINE-02 (pink #ec407a)
  | 'Tracks';       // Phase 7 DET-PIPELINE-02 (teal #26a69a)

// Port definition for node inputs/outputs
export interface PortDef {
  id: string;
  label: string;
  dataType: PortDataType;
  required: boolean;  // unconnected required ports = validation error
}

// Node categories (per CONTEXT.md: 4 categories, expanded to 7 for granularity)
// Node categories (CONTEXT.md Phase 7 D-07 adds perception)
export type NodeCategory =
  | 'sensor'
  | 'slam'
  | 'merger'
  | 'filter'
  | 'splitter'
  | 'parameter'
  | 'output'
  | 'perception';  // Phase 7 DET-PIPELINE-01 (magenta #ad1457)

// Custom node data shape
// Uses type (not interface) so it satisfies Record<string, unknown> constraint for React Flow
export type PipelineNodeData = {
  label: string;
  category: NodeCategory;
  headerColor: string;
  inputs: PortDef[];
  outputs: PortDef[];
  parameterSchema: Record<string, unknown> | null;  // JSON Schema properties subset
  paramValues: Record<string, unknown>;  // current param values
  status: 'idle' | 'processing' | 'error' | 'initializing';
  registryName?: string;  // e.g. 'icp', 'orbslam3' -- links to SLAMRegistry/MergeRegistry
  nodeType: string;  // definition key, e.g. 'sensor_rgbd', 'slam_icp'
};

// React Flow node with our custom data
export type PipelineNode = Node<PipelineNodeData>;

// Custom edge data shape
// Uses type (not interface) so it satisfies Record<string, unknown> constraint for React Flow
export type PipelineEdgeData = {
  fps: number;       // throughput (0 = idle)
  dataType: PortDataType;
};

export type PipelineEdge = Edge<PipelineEdgeData>;

// Preset metadata
export interface PresetInfo {
  name: string;
  builtIn: boolean;
  nodeCount: number;
}

// Validation error
export interface ValidationError {
  nodeId?: string;
  message: string;
}

// Serialized graph config for backend
export interface PipelineConfig {
  nodes: Array<{ id: string; type: string; params: Record<string, unknown>; position: { x: number; y: number } }>;
  edges: Array<{ source: string; sourceHandle: string; target: string; targetHandle: string }>;
}

// Node definition (template for creating instances)
export interface NodeDefinition {
  type: string;          // unique key, e.g. 'sensor_rgbd'
  label: string;
  category: NodeCategory;
  inputs: PortDef[];
  outputs: PortDef[];
  defaultParams: Record<string, unknown>;
  parameterSchema: Record<string, unknown> | null;
}

// Phase 7 revision iter 1 — lifted from App.tsx local interface so
// pipelineStore + NodeInspector + NodePalette can all share the type.
export interface RegistryNode {
  type: string;            // catalog entry key, e.g. 'detector_yolov11'
  label: string;           // display name from NodeCatalog.get_catalog()
  category: NodeCategory;
  parameterSchema: Record<string, unknown> | null;
  registryName: string;    // backend registry key, e.g. 'yolov11'
}
