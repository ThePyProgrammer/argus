import { useRef } from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import Sidebar from './components/Sidebar';
import CameraStrip from './components/CameraStrip';

/**
 * Root layout: CSS Grid with named areas.
 * "viewer sidebar" (top row, viewer takes ~70% width)
 * "cameras cameras" (bottom row, collapsible)
 */
export default function App() {
  // Establish WebSocket connection on mount
  useWebSocket();

  // Ref for the 3D scene container (Plan 03 fills this with Three.js)
  const sceneRef = useRef<HTMLDivElement>(null);

  return (
    <div className="app-container">
      <div className="viewer-area" id="scene-container" ref={sceneRef}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100%',
            color: '#333',
            fontSize: '18px',
            fontWeight: 600,
          }}
        >
          3D Viewer (Plan 03)
        </div>
      </div>
      <div className="sidebar-area">
        <Sidebar />
      </div>
      <div className="camera-strip-area">
        <CameraStrip />
      </div>
    </div>
  );
}
