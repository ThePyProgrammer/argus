import { useRobotStore } from '../stores/robotStore';
import { useControlStore } from '../stores/controlStore';

export default function WorkspaceHeader() {
  const count = useRobotStore((s) => s.robots.size);
  const connected = useControlStore((s) => s.connected);
  return <header className="workspace-header">
    <span className="brand-word">ARGUS</span>
    <div className="workspace-session">
      <span>{count} {count === 1 ? 'robot' : 'robots'}</span>
      <div className="connection-pill" role="status"><span className={`status-dot${connected ? ' connected' : ''}`} />{connected ? 'Connected' : 'Connecting'}</div>
    </div>
  </header>;
}
