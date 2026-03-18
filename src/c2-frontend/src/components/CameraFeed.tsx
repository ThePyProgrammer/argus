import { useRobotStore } from '../stores/robotStore';
import { robotColor } from '../utils/palette';

interface CameraFeedProps {
  robotId: string;
}

export default function CameraFeed({ robotId }: CameraFeedProps) {
  // Selective subscription: only re-renders when THIS robot's cameraUrl changes
  const cameraUrl = useRobotStore((s) => s.robots.get(robotId)?.cameraUrl);
  const colorIndex = useRobotStore(
    (s) => s.robots.get(robotId)?.colorIndex ?? 0,
  );
  const color = robotColor(colorIndex);

  return (
    <div
      style={{
        width: '320px',
        height: '240px',
        flexShrink: 0,
        background: '#0a0a1a',
        borderRadius: '4px',
        overflow: 'hidden',
        position: 'relative',
      }}
    >
      {/* Color accent bar */}
      <div
        style={{
          height: '3px',
          background: color,
          width: '100%',
        }}
      />
      {/* Label */}
      <div
        style={{
          position: 'absolute',
          top: '6px',
          left: '8px',
          fontSize: '11px',
          fontWeight: 600,
          background: 'rgba(0,0,0,0.6)',
          padding: '2px 6px',
          borderRadius: '3px',
          color: '#e0e0e0',
        }}
      >
        {robotId}
      </div>
      {cameraUrl ? (
        <img
          src={cameraUrl}
          alt={`${robotId} camera`}
          style={{ width: '320px', height: '237px', objectFit: 'cover' }}
        />
      ) : (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            height: '237px',
            color: '#555',
            fontSize: '13px',
          }}
        >
          No feed
        </div>
      )}
    </div>
  );
}
