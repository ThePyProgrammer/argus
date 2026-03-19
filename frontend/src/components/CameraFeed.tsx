import { useRobotStore } from '../stores/robotStore';
import { robotColor } from '../utils/palette';

interface CameraFeedProps {
  robotId: string;
}

export default function CameraFeed({ robotId }: CameraFeedProps) {
  const cameraUrl = useRobotStore((s) => s.robots.get(robotId)?.cameraUrl);
  const depthUrl = useRobotStore((s) => s.robots.get(robotId)?.depthUrl);
  const colorIndex = useRobotStore(
    (s) => s.robots.get(robotId)?.colorIndex ?? 0,
  );
  const color = robotColor(colorIndex);

  const imgStyle: React.CSSProperties = {
    width: '100%',
    height: '100%',
    objectFit: 'cover',
  };

  const noFeedStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100%',
    color: '#555',
    fontSize: '12px',
  };

  return (
    <div
      style={{
        width: '400px',
        height: '240px',
        flexShrink: 0,
        background: '#0a0a1a',
        borderRadius: '4px',
        overflow: 'hidden',
        position: 'relative',
      }}
    >
      {/* Color accent bar */}
      <div style={{ height: '3px', background: color, width: '100%' }} />
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
          zIndex: 1,
        }}
      >
        {robotId}
      </div>
      {/* Side-by-side: RGB + Depth */}
      <div style={{ display: 'flex', height: '237px' }}>
        <div style={{ flex: 1, position: 'relative' }}>
          <div style={{
            position: 'absolute', bottom: '4px', left: '4px',
            fontSize: '10px', color: '#aaa', background: 'rgba(0,0,0,0.5)',
            padding: '1px 4px', borderRadius: '2px', zIndex: 1,
          }}>RGB</div>
          {cameraUrl ? (
            <img src={cameraUrl} alt={`${robotId} rgb`} style={imgStyle} />
          ) : (
            <div style={noFeedStyle}>No RGB</div>
          )}
        </div>
        <div style={{ width: '1px', background: '#2a2a4a' }} />
        <div style={{ flex: 1, position: 'relative' }}>
          <div style={{
            position: 'absolute', bottom: '4px', left: '4px',
            fontSize: '10px', color: '#aaa', background: 'rgba(0,0,0,0.5)',
            padding: '1px 4px', borderRadius: '2px', zIndex: 1,
          }}>Depth</div>
          {depthUrl ? (
            <img src={depthUrl} alt={`${robotId} depth`} style={imgStyle} />
          ) : (
            <div style={noFeedStyle}>No depth</div>
          )}
        </div>
      </div>
    </div>
  );
}
