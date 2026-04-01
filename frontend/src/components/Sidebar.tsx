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
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Header */}
      <div
        style={{
          padding: '16px 12px 12px',
          borderBottom: '1px solid #2a2a4a',
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'baseline',
          }}
        >
          <h2
            style={{
              margin: 0,
              fontSize: '16px',
              fontWeight: 700,
              letterSpacing: '0.5px',
            }}
          >
            Argus
          </h2>
          <span style={{ fontSize: '12px', color: '#888' }}>
            {formatTime(elapsed)}
          </span>
        </div>
        <div
          style={{
            display: 'flex',
            gap: '16px',
            marginTop: '8px',
            fontSize: '12px',
            color: '#aaa',
            alignItems: 'center',
          }}
        >
          <span>Coverage: {totalCoverage.toFixed(1)}%</span>
          <span>Merges: {mergeCount}</span>
          <button
              onClick={() => setOutputHidden(!outputHidden)}
              style={{
                marginLeft: 'auto',
                background: '#2a2a4a',
                border: 'none',
                borderRadius: '4px',
                height: '28px',
                padding: '0 10px',
                fontSize: '11px',
                fontWeight: 500,
                color: '#aaa',
                cursor: 'pointer',
                whiteSpace: 'nowrap',
              }}
              onMouseEnter={(e) => { (e.currentTarget.style.background = '#3a3a5a'); }}
              onMouseLeave={(e) => { (e.currentTarget.style.background = '#2a2a4a'); }}
            >
              {outputHidden ? 'Show Output' : 'Hide Output'}
            </button>
        </div>
      </div>

      {/* Robot cards */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '8px 8px 0' }}>
        {robots.map((robot) => (
          <RobotCard key={robot.id} robot={robot} />
        ))}
        {robots.length === 0 && (
          <div
            style={{
              textAlign: 'center',
              color: '#555',
              padding: '24px',
              fontSize: '13px',
            }}
          >
            Waiting for robots...
          </div>
        )}
      </div>

      {/* Control panel at bottom */}
      <ControlPanel />
    </div>
  );
}
