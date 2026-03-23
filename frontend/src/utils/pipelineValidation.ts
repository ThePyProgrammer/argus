import type { PipelineNode, PipelineEdge, ValidationError } from './pipelineTypes';

/**
 * Detect cycles in the pipeline graph using Kahn's algorithm (topological sort).
 * Returns an array of node labels involved in cycles, or null if the graph is a valid DAG.
 */
export function detectCycles(nodes: PipelineNode[], edges: PipelineEdge[]): string[] | null {
  const inDegree = new Map<string, number>();
  const adj = new Map<string, string[]>();

  for (const node of nodes) {
    inDegree.set(node.id, 0);
    adj.set(node.id, []);
  }

  for (const edge of edges) {
    adj.get(edge.source)!.push(edge.target);
    inDegree.set(edge.target, (inDegree.get(edge.target) ?? 0) + 1);
  }

  const queue = [...inDegree.entries()]
    .filter(([, deg]) => deg === 0)
    .map(([id]) => id);

  const sorted: string[] = [];
  while (queue.length > 0) {
    const node = queue.shift()!;
    sorted.push(node);
    for (const neighbor of adj.get(node) ?? []) {
      const newDeg = (inDegree.get(neighbor) ?? 1) - 1;
      inDegree.set(neighbor, newDeg);
      if (newDeg === 0) queue.push(neighbor);
    }
  }

  if (sorted.length !== nodes.length) {
    // Nodes not in sorted set are involved in cycles
    const sortedSet = new Set(sorted);
    const cycleNodes = nodes
      .filter((n) => !sortedSet.has(n.id))
      .map((n) => n.data.label);
    return cycleNodes;
  }
  return null;
}

/**
 * Find nodes with unconnected required input ports.
 */
export function findUnconnectedPorts(nodes: PipelineNode[], edges: PipelineEdge[]): ValidationError[] {
  const errors: ValidationError[] = [];

  // Build set of connected target handles: "nodeId:handleId"
  const connectedInputs = new Set<string>();
  for (const edge of edges) {
    if (edge.targetHandle) {
      connectedInputs.add(`${edge.target}:${edge.targetHandle}`);
    }
  }

  for (const node of nodes) {
    for (const port of node.data.inputs) {
      if (port.required && !connectedInputs.has(`${node.id}:${port.id}`)) {
        errors.push({
          nodeId: node.id,
          message: `Node '${node.data.label}' has unconnected required input '${port.label}'`,
        });
      }
    }
  }

  return errors;
}

/**
 * Check that the pipeline has at least one visualization output node.
 */
export function findMissingOutput(nodes: PipelineNode[]): ValidationError | null {
  const hasOutput = nodes.some((n) => n.data.category === 'output');
  if (!hasOutput) {
    return { message: 'Pipeline has no visualization output node' };
  }
  return null;
}

/**
 * Run all graph validations. Returns combined array of errors.
 * Order: cycles first, then unconnected ports, then missing output.
 */
export function validateGraph(nodes: PipelineNode[], edges: PipelineEdge[]): ValidationError[] {
  const errors: ValidationError[] = [];

  // Check for cycles
  const cycleLabels = detectCycles(nodes, edges);
  if (cycleLabels) {
    errors.push({
      message: `Pipeline contains a cycle through nodes: ${cycleLabels.join(', ')}`,
    });
  }

  // Check for unconnected required ports
  errors.push(...findUnconnectedPorts(nodes, edges));

  // Check for missing output
  const missingOutput = findMissingOutput(nodes);
  if (missingOutput) {
    errors.push(missingOutput);
  }

  return errors;
}
