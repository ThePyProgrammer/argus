import { useState } from 'react';
import { useRobotStore, type Detection } from '../stores/robotStore';
import { robotColor } from '../utils/palette';

interface CameraFeedProps {
  robotId: string;
}

/**
 * Interactive YOLO detection overlays as positioned HTML divs.
 * Hover to highlight and see a tooltip with details.
 */
function DetectionOverlay({
  detections,
  color,
  imgWidth,
  imgHeight,
}: {
  detections: Detection[];
  color: string;
  imgWidth: number;
  imgHeight: number;
}) {
  const [hovered, setHovered] = useState<number | null>(null);

  return (
    <div style={{
      position: 'absolute', top: 0, left: 0, width: '100%', height: '100%',
      zIndex: 2,
    }}>
      {detections.map((det, i) => {
        if (!det.bbox || det.bbox.length < 4) return null;
        const [x1, y1, x2, y2] = det.bbox;

        // Convert pixel coords to percentages for responsive positioning
        const left = `${(x1 / imgWidth) * 100}%`;
        const top = `${(y1 / imgHeight) * 100}%`;
        const width = `${((x2 - x1) / imgWidth) * 100}%`;
        const height = `${((y2 - y1) / imgHeight) * 100}%`;
        const isHovered = hovered === i;

        // Determine if label/tooltip would clip at top/bottom
        const pctTop = (y1 / imgHeight) * 100;
        const pctBottom = ((imgHeight - y2) / imgHeight) * 100;
        const labelOnTop = pctTop > 5;   // enough room above?
        const tooltipOnBottom = pctBottom > 15; // enough room below?

        return (
          <div
            key={i}
            onMouseEnter={() => setHovered(i)}
            onMouseLeave={() => setHovered(null)}
            style={{
              position: 'absolute',
              left, top, width, height,
              border: `2px solid ${isHovered ? '#fff' : color}`,
              borderRadius: '2px',
              background: isHovered ? 'rgba(255,255,255,0.15)' : 'rgba(255,255,255,0.05)',
              cursor: 'pointer',
              transition: 'all 0.15s ease',
              boxShadow: isHovered ? `0 0 8px ${color}` : 'none',
            }}
          >
            {/* Label badge -- above box if room, below if not */}
            <div style={{
              position: 'absolute',
              left: 0,
              ...(labelOnTop
                ? { bottom: '100%', marginBottom: '2px' }
                : { top: '100%', marginTop: '2px' }),
              padding: '1px 5px',
              background: isHovered ? color : 'rgba(0,0,0,0.75)',
              color: isHovered ? '#000' : color,
              fontSize: '10px',
              fontWeight: 700,
              fontFamily: 'monospace',
              whiteSpace: 'nowrap',
              borderRadius: '2px',
              transition: 'all 0.15s ease',
            }}>
              {det.class} {(det.confidence * 100).toFixed(0)}%
            </div>

            {/* Tooltip on hover -- below box if room, above if not */}
            {isHovered && (
              <div style={{
                position: 'absolute',
                left: '50%',
                transform: 'translateX(-50%)',
                ...(tooltipOnBottom
                  ? { top: '100%', marginTop: '4px' }
                  : { bottom: '100%', marginBottom: '4px' }),
                padding: '6px 10px',
                background: 'rgba(0,0,0,0.9)',
                border: `1px solid ${color}`,
                borderRadius: '4px',
                fontSize: '11px',
                fontFamily: 'monospace',
                color: '#eee',
                whiteSpace: 'nowrap',
                zIndex: 10,
                pointerEvents: 'none',
              }}>
                <div><strong style={{ color }}>{det.class}</strong></div>
                <div>Confidence: {(det.confidence * 100).toFixed(1)}%</div>
                <div>BBox: [{det.bbox.join(', ')}]</div>
                {det.pos_3d && (
                  <div>3D: [{det.pos_3d.map(v => v.toFixed(2)).join(', ')}]</div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

export default function CameraFeed({ robotId }: CameraFeedProps) {
  const cameraUrl = useRobotStore((s) => s.robots.get(robotId)?.cameraUrl);
  const depthUrl = useRobotStore((s) => s.robots.get(robotId)?.depthUrl);
  const detections = useRobotStore((s) => s.robots.get(robotId)?.detections ?? []);
  const colorIndex = useRobotStore(
    (s) => s.robots.get(robotId)?.colorIndex ?? 0,
  );
  const color = robotColor(colorIndex);

  // Images are rotated server-side (cv2.rotate in encode_camera_frame)
  // so no CSS rotation needed.
  const imgStyle: React.CSSProperties = {
    width: '100%',
    height: 'auto',
    display: 'block',
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
          zIndex: 3,
        }}
      >
        {robotId}
      </div>
      {/* Side-by-side: RGB (with detection overlay) + Depth */}
      <div style={{ display: 'flex', height: 'calc(100% - 3px)' }}>
        <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
          <div style={{
            position: 'absolute', bottom: '4px', left: '4px',
            fontSize: '10px', color: '#aaa', background: 'rgba(0,0,0,0.5)',
            padding: '1px 4px', borderRadius: '2px', zIndex: 3,
          }}>RGB</div>
          {cameraUrl ? (
            <>
              <img src={cameraUrl} alt={`${robotId} rgb`} style={imgStyle} />
              {/* YOLO detection overlay (interactive) */}
              <DetectionOverlay
                detections={detections}
                color={color}
                imgWidth={480}
                imgHeight={640}
              />
            </>
          ) : (
            <div style={noFeedStyle}>No RGB</div>
          )}
        </div>
        <div style={{ width: '1px', background: '#2a2a4a' }} />
        <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
          <div style={{
            position: 'absolute', bottom: '4px', left: '4px',
            fontSize: '10px', color: '#aaa', background: 'rgba(0,0,0,0.5)',
            padding: '1px 4px', borderRadius: '2px', zIndex: 3,
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
