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
      {/* Scene description from VLM */}
      {robot.sceneDescription && (
        <div style={{
          marginTop: '6px', padding: '4px 6px', background: '#1a1a3a',
          borderRadius: '4px', fontSize: '11px', color: '#9ca3af',
          fontStyle: 'italic', lineHeight: '1.3',
        }}>
          🔍 {robot.sceneDescription}
        </div>
      )}

      {/* YOLO detections */}
      {robot.detections.length > 0 && (
        <div style={{
          marginTop: '4px', fontSize: '11px', color: '#aaa',
          display: 'flex', flexWrap: 'wrap', gap: '3px',
        }}>
          {robot.detections.slice(0, 8).map((det, i) => (
            <span key={i} style={{
              padding: '1px 5px', background: '#2a2a4a', borderRadius: '3px',
              fontSize: '10px',
            }}>
              {det.class} {(det.confidence * 100).toFixed(0)}%
            </span>
          ))}
          {robot.detections.length > 8 && (
            <span style={{ fontSize: '10px', color: '#666' }}>
              +{robot.detections.length - 8} more
            </span>
          )}
        </div>
      )}

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
