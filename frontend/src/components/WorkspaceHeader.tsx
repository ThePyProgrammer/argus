import { useRobotStore } from '../stores/robotStore';
import { useControlStore } from '../stores/controlStore';
import { useSimulationStore } from '../stores/simulationStore';

export default function WorkspaceHeader() {
  const count = useRobotStore((s) => s.robots.size);
  const connected = useControlStore((s) => s.connected);
  const loading = useSimulationStore((s) => s.status.phase === 'loading');
  const openRestart = useControlStore((s) => s.setRestartPickerOpen);
  return <header className="workspace-header">
    <span className="brand-word">ARGUS</span>
    <div className="workspace-session">
      <button className="quiet-button" disabled={!connected || loading} onClick={() => openRestart(true)}>Restart</button>
      <span>{count} {count === 1 ? 'robot' : 'robots'}</span>
      <div className="connection-pill" role="status"><span className={`status-dot${connected ? ' connected' : ''}`} />{connected ? 'Connected' : 'Connecting'}</div>
    </div>
  </header>;
}
