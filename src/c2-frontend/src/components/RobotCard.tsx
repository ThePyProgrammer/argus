import type { RobotInfo } from '../stores/robotStore';
import { robotColor } from '../utils/palette';

interface RobotCardProps {
  robot: RobotInfo;
}

export default function RobotCard({ robot }: RobotCardProps) {
  const color = robotColor(robot.colorIndex);

  const handleClick = () => {
    // Dispatch custom event for Plan 03 to listen to (center camera on robot)
    window.dispatchEvent(
      new CustomEvent('focus-robot', { detail: { robotId: robot.id } }),
    );
  };

  return (
    <div
      className="robot-card"
      onClick={handleClick}
      style={{
        padding: '10px 12px',
        marginBottom: '6px',
        background: '#222244',
        borderRadius: '6px',
        cursor: 'pointer',
        borderLeft: `3px solid ${color}`,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span
          style={{
            width: '10px',
            height: '10px',
            borderRadius: '50%',
            background: '#4caf50',
            display: 'inline-block',
            flexShrink: 0,
          }}
        />
        <span style={{ fontWeight: 600, fontSize: '14px' }}>{robot.id}</span>
        <span
          style={{
            marginLeft: 'auto',
            fontSize: '12px',
            color: '#aaa',
            textTransform: 'capitalize',
          }}
        >
          {robot.action}
        </span>
      </div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          marginTop: '6px',
          fontSize: '12px',
          color: '#bbb',
        }}
      >
        <span>Coverage: {robot.coveragePct.toFixed(1)}%</span>
        <span>Voxels: {robot.voxelCount.toLocaleString()}</span>
      </div>
    </div>
  );
}
