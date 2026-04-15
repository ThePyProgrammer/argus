import type { PipelineNode, PipelineEdge, PipelineConfig, NodeDefinition, PortDataType } from './pipelineTypes';
import { buildNodeData } from './nodeDefinitions';

/**
 * Serialize React Flow graph state to backend-compatible JSON config.
 * Resolves custom parameter node overrides via edge traversal:
 * if an edge source node has category 'parameter', its paramValues.value
 * overrides the target node's param matching the target handle name.
 */
export function serializeGraph(nodes: PipelineNode[], edges: PipelineEdge[]): PipelineConfig {
  // Build a lookup of node id -> node for parameter resolution
  const nodeMap = new Map<string, PipelineNode>();
  for (const node of nodes) {
    nodeMap.set(node.id, node);
  }

  // For each node, start with its own paramValues, then apply parameter node overrides
  const resolvedParams = new Map<string, Record<string, unknown>>();
  for (const node of nodes) {
    resolvedParams.set(node.id, { ...node.data.paramValues });
  }

  // Traverse edges: if source is a parameter node, override target's param
  for (const edge of edges) {
    const sourceNode = nodeMap.get(edge.source);
    if (sourceNode && sourceNode.data.category === 'parameter') {
      const paramValue = sourceNode.data.paramValues.value;
      const targetHandle = edge.targetHandle;
      if (targetHandle && paramValue !== undefined) {
        const targetParams = resolvedParams.get(edge.target);
        if (targetParams) {
          targetParams[targetHandle] = paramValue;
        }
      }
    }
  }

  return {
    nodes: nodes.map((node) => ({
      id: node.id,
      type: node.data.nodeType,
      params: resolvedParams.get(node.id) ?? {},
      position: { x: node.position.x, y: node.position.y },
    })),
    edges: edges.map((edge) => ({
      source: edge.source,
      sourceHandle: edge.sourceHandle ?? '',
      target: edge.target,
      targetHandle: edge.targetHandle ?? '',
    })),
  };
}

/**
 * Deserialize a backend pipeline config back into React Flow nodes and edges.
 * Uses buildNodeData() to reconstruct node data from definitions.
 */
export function deserializeGraph(
  config: PipelineConfig,
  existingDefinitions: Record<string, NodeDefinition>,
): { nodes: PipelineNode[]; edges: PipelineEdge[] } {
  const nodes: PipelineNode[] = config.nodes.map((configNode) => {
    // Find matching definition: exact type match first, then prefix match
    // (e.g. "slam_icp" matches "slam_generic", "merger_icp_union" matches "merger_generic")
    const defKey = Object.keys(existingDefinitions).find(
      (key) => existingDefinitions[key].type === configNode.type,
    ) ?? Object.keys(existingDefinitions).find((key) => {
      const prefix = configNode.type.split('_')[0];
      return existingDefinitions[key].type.startsWith(prefix + '_');
    });

    const data = defKey
      ? buildNodeData(defKey)
      : {
          label: configNode.type,
          category: 'filter' as const,
          headerColor: '#7b1fa2',
          inputs: [],
          outputs: [],
          parameterSchema: null,
          paramValues: {},
          status: 'idle' as const,
          nodeType: configNode.type,
        };

    // Preserve the actual backend type from config (not the generic definition type)
    data.nodeType = configNode.type;
    // Use a readable label derived from the type if it was resolved via generic fallback
    if (defKey && existingDefinitions[defKey].type !== configNode.type) {
      const readable = configNode.type.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
      data.label = readable;
    }

    // Apply saved param values
    data.paramValues = { ...data.paramValues, ...configNode.params };

    return {
      id: configNode.id,
      type: 'pipeline',
      position: configNode.position,
      data,
    };
  });

  const edges: PipelineEdge[] = config.edges.map((configEdge, index) => {
    // Phase 7 DET-PIPELINE-03 D-08 — resolve edge dataType from source node's output port.
    // Fixes former hardcoded `dataType: 'PointCloud'` at line 112.
    const sourceNode = nodes.find((n) => n.id === configEdge.source);
    const sourcePort = sourceNode?.data.outputs.find(
      (p) => p.id === configEdge.sourceHandle,
    );
    const dataType: PortDataType = sourcePort?.dataType ?? 'PointCloud';
    return {
      id: `e-${configEdge.source}-${configEdge.target}-${index}`,
      source: configEdge.source,
      sourceHandle: configEdge.sourceHandle,
      target: configEdge.target,
      targetHandle: configEdge.targetHandle,
      type: 'animated',
      data: { fps: 0, dataType },
    };
  });

  return { nodes, edges };
}
