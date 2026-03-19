import { useWebSocket } from './hooks/useWebSocket';
import Sidebar from './components/Sidebar';
import CameraStrip from './components/CameraStrip';
import SceneViewer from './components/SceneViewer';

/**
 * Root layout: CSS Grid with named areas.
 * "viewer sidebar" (top row, viewer takes ~70% width)
 * "cameras cameras" (bottom row, collapsible)
 */
export default function App() {
  // Establish WebSocket connection on mount
  useWebSocket();

  return (
    <div className="app-container">
      <div className="viewer-area" id="scene-container">
        <SceneViewer />
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
