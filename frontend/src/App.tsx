import { useState, useEffect } from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import Sidebar from './components/Sidebar';
import CameraStrip from './components/CameraStrip';
import SceneViewer from './components/SceneViewer';
import MetricsPanel from './components/MetricsPanel';
import { ViewToggle } from './components/ViewToggle';
import type { ViewMode } from './components/ViewToggle';
import { PipelineEditor } from './components/pipeline/PipelineEditor';
import { NodePalette } from './components/pipeline/NodePalette';
import { NodeInspector } from './components/pipeline/NodeInspector';
import { ApplyBar } from './components/pipeline/ApplyBar';
import { usePipelineStore } from './stores/pipelineStore';
import { deserializeGraph } from './utils/pipelineSerializer';
import { NODE_DEFINITIONS } from './utils/nodeDefinitions';
import type { PipelineNode, PipelineEdge } from './utils/pipelineTypes';

interface RegistryNode {
  type: string;
  label: string;
  category: 'sensor' | 'slam' | 'merger' | 'filter' | 'splitter' | 'parameter' | 'output';
  parameterSchema: Record<string, unknown> | null;
  registryName: string;
}

function InspectorWrapper() {
  const selectedNodeId = usePipelineStore((s) => s.selectedNodeId);
  if (!selectedNodeId) return null;
  return <NodeInspector />;
}

/**
 * Root layout: CSS Grid with named areas.
 * "viewer sidebar" (top row, viewer takes ~70% width)
 * "cameras cameras" (bottom row, collapsible)
 */
export default function App() {
  // Establish WebSocket connection on mount
  useWebSocket();

  const [activeView, setActiveView] = useState<ViewMode>('3d');
  const [paletteCollapsed, setPaletteCollapsed] = useState(false);
  const [registryNodes, setRegistryNodes] = useState<RegistryNode[]>([]);
  const [outputHidden, setOutputHidden] = useState(false);

  // Fetch node catalog and load default preset when switching to pipeline view
  useEffect(() => {
    if (activeView === 'pipeline') {
      fetch('/api/pipeline/node-catalog')
        .then((r) => r.json())
        .then((data) => {
          const regNodes = (data.nodes ?? [])
            .filter((n: Record<string, unknown>) => n.registryName)
            .map((n: Record<string, unknown>) => ({
              type: n.type as string,
              label: n.label as string,
              category: n.category as RegistryNode['category'],
              parameterSchema: n.parameterSchema as Record<string, unknown> | null,
              registryName: n.registryName as string,
            }));
          setRegistryNodes(regNodes);
        })
        .catch(() => {});

      // Load "Default ICP" preset if graph is empty (first open)
      const store = usePipelineStore.getState();
      if (store.nodes.length === 0) {
        fetch('/api/pipeline/presets/default_icp')
          .then((r) => {
            if (!r.ok) throw new Error(`preset fetch failed: ${r.status}`);
            return r.json();
          })
          .then((data) => {
            if (data.nodes && data.edges) {
              const { nodes, edges } = deserializeGraph(
                { nodes: data.nodes, edges: data.edges },
                NODE_DEFINITIONS,
              );
              usePipelineStore.getState().loadPresetGraph(
                nodes as PipelineNode[],
                edges as PipelineEdge[],
                data.name ?? 'Default ICP',
              );
            }
          })
          .catch(() => {});
      }
    }
  }, [activeView]);

  return (
    <div className={outputHidden ? 'app-container output-hidden' : 'app-container'}>
      {!outputHidden && (
        <div className="viewer-area" id="scene-container" style={{ position: 'relative' }}>
          <ViewToggle activeView={activeView} onViewChange={setActiveView} />
          {activeView === '3d' ? (
            <SceneViewer />
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
              <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
                <NodePalette
                  collapsed={paletteCollapsed}
                  onToggleCollapse={() => setPaletteCollapsed((c) => !c)}
                  registryNodes={registryNodes}
                />
                <div style={{ flex: 1, position: 'relative' }}>
                  <PipelineEditor />
                </div>
                <InspectorWrapper />
              </div>
              <ApplyBar />
            </div>
          )}
        </div>
      )}
      <div className="sidebar-area">
        <Sidebar
          outputHidden={outputHidden}
          onToggleOutput={() => setOutputHidden((h) => !h)}
        />
      </div>
      {!outputHidden && (
        <div className="metrics-area">
          <MetricsPanel />
        </div>
      )}
      {!outputHidden && (
        <div className="camera-strip-area">
          <CameraStrip />
        </div>
      )}
    </div>
  );
}
