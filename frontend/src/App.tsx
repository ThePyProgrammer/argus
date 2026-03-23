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

  // Fetch node catalog when switching to pipeline view
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
    }
  }, [activeView]);

  return (
    <div className="app-container">
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
      <div className="sidebar-area">
        <Sidebar />
      </div>
      <div className="metrics-area">
        <MetricsPanel />
      </div>
      <div className="camera-strip-area">
        <CameraStrip />
      </div>
    </div>
  );
}
