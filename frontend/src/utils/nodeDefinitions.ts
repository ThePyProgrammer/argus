import type { PortDataType, NodeCategory, NodeDefinition, PipelineNodeData } from './pipelineTypes';

// Port socket colors per data type (from UI-SPEC)
export const PORT_COLORS: Record<PortDataType, string> = {
  Image: '#42a5f5',
  PointCloud: '#66bb6a',
  Pose: '#ffa726',
  IMU: '#ab47bc',
  Scalar: '#ef5350',
  Boolean: '#78909c',
  Config: '#ffee58',
  // Phase 7 DET-PIPELINE-02 (CONTEXT D-07)
  Detections2D: '#ff8a65',  // coral
  Detections3D: '#ec407a',  // pink
  Tracks: '#26a69a',        // teal
};

// Port socket shapes per data type (from UI-SPEC)
export const PORT_SHAPES: Record<PortDataType, string> = {
  Image: 'circle',
  PointCloud: 'circle',
  Pose: 'circle',
  IMU: 'circle',
  Scalar: 'diamond',
  Boolean: 'diamond',
  Config: 'square',
  // Phase 7 — streaming envelopes = circle (UI-SPEC Color rationale)
  Detections2D: 'circle',
  Detections3D: 'circle',
  Tracks: 'circle',
};

// Node header colors per category (from UI-SPEC)
export const CATEGORY_COLORS: Record<NodeCategory, string> = {
  sensor: '#1565c0',
  slam: '#2e7d32',
  merger: '#e65100',
  filter: '#7b1fa2',
  splitter: '#00838f',
  parameter: '#6d4c41',
  output: '#c62828',
  // Phase 7 DET-PIPELINE-01 (CONTEXT D-07)
  perception: '#ad1457',  // magenta
};

// Static node type definitions
export const NODE_DEFINITIONS: Record<string, NodeDefinition> = {
  sensor_rgbd: {
    type: 'sensor_rgbd',
    label: 'RGB-D Sensor',
    category: 'sensor',
    inputs: [],
    outputs: [
      { id: 'image_out', label: 'RGB', dataType: 'Image', required: false },
      { id: 'depth_out', label: 'Depth', dataType: 'Image', required: false },
    ],
    defaultParams: {},
    parameterSchema: null,
  },

  sensor_imu: {
    type: 'sensor_imu',
    label: 'IMU Sensor',
    category: 'sensor',
    inputs: [],
    outputs: [
      { id: 'imu_out', label: 'IMU', dataType: 'IMU', required: false },
    ],
    defaultParams: {},
    parameterSchema: null,
  },

  slam_generic: {
    type: 'slam_generic',
    label: 'SLAM Backend',
    category: 'slam',
    inputs: [
      { id: 'image_in', label: 'Image', dataType: 'Image', required: true },
      { id: 'imu_in', label: 'IMU', dataType: 'IMU', required: false },
    ],
    outputs: [
      { id: 'pose_out', label: 'Pose', dataType: 'Pose', required: false },
      { id: 'cloud_out', label: 'PointCloud', dataType: 'PointCloud', required: false },
    ],
    defaultParams: {},
    parameterSchema: null,  // populated from registry at runtime
  },

  merger_generic: {
    type: 'merger_generic',
    label: 'Map Merger',
    category: 'merger',
    inputs: [
      { id: 'cloud_in', label: 'PointCloud', dataType: 'PointCloud', required: true },
      { id: 'pose_in', label: 'Pose', dataType: 'Pose', required: true },
    ],
    outputs: [
      { id: 'merged_out', label: 'Merged Cloud', dataType: 'PointCloud', required: false },
    ],
    defaultParams: {},
    parameterSchema: null,  // populated from registry at runtime
  },

  filter_voxel_downsample: {
    type: 'filter_voxel_downsample',
    label: 'Voxel Downsample',
    category: 'filter',
    inputs: [
      { id: 'cloud_in', label: 'PointCloud', dataType: 'PointCloud', required: true },
    ],
    outputs: [
      { id: 'cloud_out', label: 'Filtered', dataType: 'PointCloud', required: false },
    ],
    defaultParams: { voxel_size: 0.05 },
    parameterSchema: {
      type: 'object',
      properties: {
        voxel_size: {
          type: 'number',
          minimum: 0.001,
          maximum: 1.0,
          default: 0.05,
          description: 'Voxel size for downsampling',
          primary: true,
          live_tunable: true,
        },
      },
    },
  },

  filter_noise_removal: {
    type: 'filter_noise_removal',
    label: 'Noise Removal',
    category: 'filter',
    inputs: [
      { id: 'cloud_in', label: 'PointCloud', dataType: 'PointCloud', required: true },
    ],
    outputs: [
      { id: 'cloud_out', label: 'Cleaned', dataType: 'PointCloud', required: false },
    ],
    defaultParams: { nb_neighbors: 20, std_ratio: 2.0 },
    parameterSchema: {
      type: 'object',
      properties: {
        nb_neighbors: {
          type: 'integer',
          minimum: 1,
          maximum: 100,
          default: 20,
          description: 'Number of neighbors for statistical outlier removal',
          primary: true,
          live_tunable: true,
        },
        std_ratio: {
          type: 'number',
          minimum: 0.1,
          maximum: 10.0,
          default: 2.0,
          description: 'Standard deviation ratio threshold',
          primary: true,
          live_tunable: true,
        },
      },
    },
  },

  filter_coord_transform: {
    type: 'filter_coord_transform',
    label: 'Coordinate Transform',
    category: 'filter',
    inputs: [
      { id: 'pose_in', label: 'Pose', dataType: 'Pose', required: true },
    ],
    outputs: [
      { id: 'pose_out', label: 'Transformed', dataType: 'Pose', required: false },
    ],
    defaultParams: { scale: 1.0 },
    parameterSchema: {
      type: 'object',
      properties: {
        scale: {
          type: 'number',
          minimum: 0.001,
          maximum: 1000.0,
          default: 1.0,
          description: 'Scale factor for coordinate transform',
          primary: true,
          live_tunable: true,
        },
      },
    },
  },

  splitter: {
    type: 'splitter',
    label: 'Stream Splitter',
    category: 'splitter',
    inputs: [
      { id: 'data_in', label: 'Input', dataType: 'PointCloud', required: true },
    ],
    outputs: [
      { id: 'out_a', label: 'Output A', dataType: 'PointCloud', required: false },
      { id: 'out_b', label: 'Output B', dataType: 'PointCloud', required: false },
    ],
    defaultParams: {},
    parameterSchema: null,
  },

  combiner: {
    type: 'combiner',
    label: 'Stream Combiner',
    category: 'splitter',  // same visual category as splitter
    inputs: [
      { id: 'in_a', label: 'Input A', dataType: 'PointCloud', required: true },
      { id: 'in_b', label: 'Input B', dataType: 'PointCloud', required: true },
    ],
    outputs: [
      { id: 'data_out', label: 'Combined', dataType: 'PointCloud', required: false },
    ],
    defaultParams: {},
    parameterSchema: null,
  },

  param_scalar: {
    type: 'param_scalar',
    label: 'Scalar Constant',
    category: 'parameter',
    inputs: [],
    outputs: [
      { id: 'value_out', label: 'Value', dataType: 'Scalar', required: false },
    ],
    defaultParams: { value: 0.0 },
    parameterSchema: {
      type: 'object',
      properties: {
        value: {
          type: 'number',
          default: 0,
          description: 'Constant scalar value',
          primary: true,
          live_tunable: true,
        },
      },
    },
  },

  // ---- Phase 7 DET-PIPELINE-01 perception nodes ----
  detector_generic: {
    type: 'detector_generic',
    label: 'Detector',
    category: 'perception',
    inputs: [
      { id: 'image_in', label: 'Image', dataType: 'Image', required: true },
      { id: 'depth_in', label: 'Depth', dataType: 'Image', required: false },
    ],
    outputs: [
      { id: 'detections_2d_out', label: 'Detections 2D', dataType: 'Detections2D', required: false },
      { id: 'detections_3d_out', label: 'Detections 3D', dataType: 'Detections3D', required: false },
    ],
    defaultParams: {},
    parameterSchema: null,
  },

  detection3d_generic: {
    type: 'detection3d_generic',
    label: '3D Lifter',
    category: 'perception',
    inputs: [
      { id: 'detections_2d_in', label: 'Detections 2D', dataType: 'Detections2D', required: true },
      { id: 'depth_in', label: 'Depth', dataType: 'Image', required: true },
      { id: 'pose_in', label: 'Pose', dataType: 'Pose', required: false },
    ],
    outputs: [
      { id: 'detections_3d_out', label: 'Detections 3D', dataType: 'Detections3D', required: false },
    ],
    defaultParams: {},
    parameterSchema: null,
  },

  tracker_generic: {
    type: 'tracker_generic',
    label: 'Tracker',
    category: 'perception',
    inputs: [
      { id: 'detections_3d_in', label: 'Detections 3D', dataType: 'Detections3D', required: true },
    ],
    outputs: [
      { id: 'tracks_out', label: 'Tracks', dataType: 'Tracks', required: false },
    ],
    defaultParams: {},
    parameterSchema: null,
  },

  viz_output: {
    type: 'viz_output',
    label: 'Visualization Output',
    category: 'output',
    inputs: [
      { id: 'cloud_in', label: 'PointCloud', dataType: 'PointCloud', required: true },
      { id: 'pose_in', label: 'Pose', dataType: 'Pose', required: false },
      // Phase 7 DET-PIPELINE-01 D-06
      { id: 'tracks_in', label: 'Tracks', dataType: 'Tracks', required: false },
    ],
    outputs: [],
    defaultParams: {},
    parameterSchema: null,
  },
};

/**
 * Build a PipelineNodeData object from a node definition key.
 * Optionally merges registry-provided schema and name.
 */
export function buildNodeData(
  defKey: string,
  registryName?: string,
  registrySchema?: Record<string, unknown>,
): PipelineNodeData {
  const def = NODE_DEFINITIONS[defKey];
  if (!def) {
    throw new Error(`Unknown node definition: ${defKey}`);
  }

  const schema = registrySchema ?? def.parameterSchema;

  return {
    label: def.label,
    category: def.category,
    headerColor: CATEGORY_COLORS[def.category],
    inputs: [...def.inputs],
    outputs: [...def.outputs],
    parameterSchema: schema ? { ...schema } : null,
    paramValues: { ...def.defaultParams },
    status: 'idle',
    registryName: registryName,
    nodeType: def.type,
  };
}
