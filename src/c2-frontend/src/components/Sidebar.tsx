import { useRobotStore } from '../stores/robotStore';
import RobotCard from './RobotCard';
import ControlPanel from './ControlPanel';

export default function Sidebar() {
  const robots = useRobotStore((s) => [...s.robots.values()]);
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
            C2 Command
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
          }}
        >
          <span>Coverage: {totalCoverage.toFixed(1)}%</span>
          <span>Merges: {mergeCount}</span>
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
