import {
  ReactFlow,
  ReactFlowProvider,
  MiniMap,
  Background,
  BackgroundVariant,
  useReactFlow,
} from '@xyflow/react';
import type { Connection, IsValidConnection } from '@xyflow/react';
import type { PipelineEdge } from '../../utils/pipelineTypes';
import '@xyflow/react/dist/style.css';
import { useCallback } from 'react';

import { nodeTypes } from './PipelineNode';
import { edgeTypes } from './EdgeAnimated';
import { usePipelineStore } from '../../stores/pipelineStore';

/**
 * Inner editor component (must be inside ReactFlowProvider to use useReactFlow).
 */
function PipelineEditorInner() {
  const nodes = usePipelineStore((s) => s.nodes);
  const edges = usePipelineStore((s) => s.edges);
  const onNodesChange = usePipelineStore((s) => s.onNodesChange);
  const onEdgesChange = usePipelineStore((s) => s.onEdgesChange);
  const onConnect = usePipelineStore((s) => s.onConnect);
  const addNode = usePipelineStore((s) => s.addNode);
  const selectNode = usePipelineStore((s) => s.selectNode);

  // Connection validation: read from store getState to avoid stale closure (Pitfall 4)
  const isValidConnection: IsValidConnection<PipelineEdge> = useCallback((connection: Connection | PipelineEdge) => {
    const currentNodes = usePipelineStore.getState().nodes;
    const sourceNode = currentNodes.find((n) => n.id === connection.source);
    const targetNode = currentNodes.find((n) => n.id === connection.target);
    if (!sourceNode || !targetNode) return false;

    const sourcePort = sourceNode.data.outputs.find(
      (p) => p.id === connection.sourceHandle,
    );
    const targetPort = targetNode.data.inputs.find(
      (p) => p.id === connection.targetHandle,
    );
    if (!sourcePort || !targetPort) return false;

    return sourcePort.dataType === targetPort.dataType;
  }, []);

  // Drag-and-drop from palette (Pattern 3 from RESEARCH.md)
  const { screenToFlowPosition } = useReactFlow();

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const rawData = event.dataTransfer.getData('application/pipeline-node');
      if (!rawData) return;
      const { defKey, registryName, registrySchema } = JSON.parse(rawData);
      const position = screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });
      addNode(defKey, position, registryName, registrySchema);
    },
    [screenToFlowPosition, addNode],
  );

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  // Click canvas to deselect node
  const onPaneClick = useCallback(() => {
    selectNode(null);
  }, [selectNode]);

  return (
    <div
      style={{ width: '100%', height: '100%', background: '#0a0a14' }}
      onDrop={onDrop}
      onDragOver={onDragOver}
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        isValidConnection={isValidConnection}
        defaultEdgeOptions={{ type: 'animated' }}
        onPaneClick={onPaneClick}
        fitView
        proOptions={{ hideAttribution: true }}
      >
        <MiniMap
          style={{ width: 160, height: 120, bottom: 16, right: 16, backgroundColor: '#0a0a14' }}
          nodeStrokeWidth={3}
          nodeColor="#1e1e32"
          maskColor="rgba(10, 10, 20, 0.7)"
          pannable
          zoomable
        />
        <Background variant={BackgroundVariant.Dots} color="#1a1a2e" gap={20} />
      </ReactFlow>
    </div>
  );
}

/**
 * Root React Flow canvas wrapper.
 * Wraps inner editor in ReactFlowProvider as required by @xyflow/react.
 */
export function PipelineEditor() {
  return (
    <ReactFlowProvider>
      <PipelineEditorInner />
    </ReactFlowProvider>
  );
}
