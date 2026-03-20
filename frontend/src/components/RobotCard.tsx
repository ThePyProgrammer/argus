import type { RobotInfo } from '../stores/robotStore';
import { useControlStore } from '../stores/controlStore';
import { robotColor } from '../utils/palette';

interface RobotCardProps {
  robot: RobotInfo;
}

export default function RobotCard({ robot }: RobotCardProps) {
  const color = robotColor(robot.colorIndex);
  const placingRobot = useControlStore((s) => s.placingRobot);
  const setPlacingRobot = useControlStore((s) => s.setPlacingRobot);

  const handleClick = () => {
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
      <button
        onClick={(e) => {
          e.stopPropagation();
          setPlacingRobot(placingRobot === robot.id ? null : robot.id);
        }}
        style={{
          marginTop: '6px',
          padding: '4px 10px',
          width: '100%',
          border: placingRobot === robot.id ? '1px solid #ff9800' : '1px solid #555',
          borderRadius: '4px',
          cursor: 'pointer',
          fontSize: '11px',
          fontWeight: 600,
          background: placingRobot === robot.id ? '#4a2800' : '#1a1a2e',
          color: placingRobot === robot.id ? '#ff9800' : '#aaa',
        }}
      >
        {placingRobot === robot.id ? 'Cancel — Click scene to place' : 'Send To...'}
      </button>
    </div>
  );
}
