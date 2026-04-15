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
 * Find edges whose source output and target input have different PortDataTypes.
 * Emits a ValidationError per mismatched edge with the CONTEXT D-09 literal message format.
 */
export function findPortTypeMismatches(
  nodes: PipelineNode[],
  edges: PipelineEdge[],
): ValidationError[] {
  const errors: ValidationError[] = [];
  const nodeById = new Map<string, PipelineNode>();
  for (const n of nodes) nodeById.set(n.id, n);

  for (const edge of edges) {
    const src = nodeById.get(edge.source);
    const tgt = nodeById.get(edge.target);
    if (!src || !tgt) continue; // defensive

    const srcPort = src.data.outputs.find((p) => p.id === edge.sourceHandle);
    const tgtPort = tgt.data.inputs.find((p) => p.id === edge.targetHandle);
    if (!srcPort || !tgtPort) continue; // handle not resolved

    if (srcPort.dataType !== tgtPort.dataType) {
      errors.push({
        nodeId: edge.target,
        message:
          `Edge from ${src.data.label}.${srcPort.label} (${srcPort.dataType}) ` +
          `to ${tgt.data.label}.${tgtPort.label} (${tgtPort.dataType}) ` +
          `has mismatched types`,
      });
    }
  }

  return errors;
}

/**
 * Run all graph validations. Returns combined array of errors.
 * Order (CONTEXT D-09): cycles → type mismatches → unconnected ports → missing output.
 * Type errors come before unconnected errors because they are more actionable
 * (user sees the specific mismatched edge, not a generic "required input missing").
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

  // Phase 7 D-09: type mismatches before structural errors.
  errors.push(...findPortTypeMismatches(nodes, edges));

  // Check for unconnected required ports
  errors.push(...findUnconnectedPorts(nodes, edges));

  // Check for missing output
  const missingOutput = findMissingOutput(nodes);
  if (missingOutput) {
    errors.push(missingOutput);
  }

  return errors;
}
