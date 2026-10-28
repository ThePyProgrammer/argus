import { useRef } from 'react';
import { useRobotStore, type RobotInfo } from '../stores/robotStore';
import { useMetricsStore } from '../stores/metricsStore';
import RobotCard from './RobotCard';
import ControlPanel from './ControlPanel';

/** Shallow-compare two arrays of robots by id + key fields to avoid re-render storms. */
function useStableRobotList(): RobotInfo[] {
  const prevRef = useRef<RobotInfo[]>([]);
  const robots = useRobotStore((s) => {
    const next = [...s.robots.values()];
    const prev = prevRef.current;
    if (
      prev.length === next.length &&
      prev.every((r, i) => r.id === next[i].id && r.coveragePct === next[i].coveragePct && r.action === next[i].action && r.voxelCount === next[i].voxelCount)
    ) {
      return prev;
    }
    prevRef.current = next;
    return next;
  });
  return robots;
}

export default function Sidebar() {
  const outputHidden = useMetricsStore((s) => s.outputHidden);
  const setOutputHidden = useMetricsStore((s) => s.setOutputHidden);
  const robots = useStableRobotList();
  const totalCoverage = useRobotStore((s) => s.totalCoverage);
  const mergeCount = useRobotStore((s) => s.mergeCount);
  const elapsed = useRobotStore((s) => s.elapsed);

  const formatTime = (seconds: number): string => {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  return (
    <aside className="sidebar-shell" aria-label="Session controls">
      <div className="fleet-header">
        <div className="fleet-heading"><h2>Session</h2><span className="session-clock">{formatTime(elapsed)}</span></div>
        <div className="session-stats"><span>Coverage <strong>{totalCoverage.toFixed(1)}%</strong></span><span>Merges <strong>{mergeCount}</strong></span></div>
      </div>
      <div className="fleet-list">
        <div className="fleet-list-heading"><span className="eyebrow">Robots / {robots.length.toString().padStart(2, '0')}</span><button className="quiet-button" onClick={() => setOutputHidden(!outputHidden)}>{outputHidden ? 'Show map output' : 'Hide map output'}</button></div>
        {robots.map((robot) => <RobotCard key={robot.id} robot={robot} />)}
        {robots.length === 0 && <div style={{ padding: '22px 10px', color: 'var(--muted)', fontSize: 12, lineHeight: 1.7 }}>Waiting for your robots.<br />They will appear when the session connects.</div>}
      </div>
      <ControlPanel />
    </aside>
  );
}
