import type { PipelineNode, PipelineEdge, PipelineConfig, NodeDefinition } from './pipelineTypes';
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
    // Find matching definition
    const defKey = Object.keys(existingDefinitions).find(
      (key) => existingDefinitions[key].type === configNode.type,
    );

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

    // Apply saved param values
    data.paramValues = { ...data.paramValues, ...configNode.params };

    return {
      id: configNode.id,
      type: 'pipeline',
      position: configNode.position,
      data,
    };
  });

  const edges: PipelineEdge[] = config.edges.map((configEdge, index) => ({
    id: `e-${configEdge.source}-${configEdge.target}-${index}`,
    source: configEdge.source,
    sourceHandle: configEdge.sourceHandle,
    target: configEdge.target,
    targetHandle: configEdge.targetHandle,
    type: 'animated',
    data: { fps: 0, dataType: 'PointCloud' as const },
  }));

  return { nodes, edges };
}
