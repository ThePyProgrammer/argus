import { useEffect, useRef } from 'react';
import { useRobotStore, type Detection } from '../stores/robotStore';
import { robotColor } from '../utils/palette';

interface CameraFeedProps {
  robotId: string;
}

/**
 * Draw YOLO bounding boxes on a canvas overlaying the RGB image.
 */
function DetectionOverlay({
  detections,
  color,
  width,
  height,
}: {
  detections: Detection[];
  color: string;
  width: number;
  height: number;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.clearRect(0, 0, width, height);

    for (const det of detections) {
      if (!det.bbox || det.bbox.length < 4) continue;
      const [x1, y1, x2, y2] = det.bbox;

      // Draw box
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);

      // Draw label background
      const label = `${det.class} ${(det.confidence * 100).toFixed(0)}%`;
      ctx.font = 'bold 12px monospace';
      const textWidth = ctx.measureText(label).width;
      ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
      ctx.fillRect(x1, y1 - 16, textWidth + 6, 16);

      // Draw label text
      ctx.fillStyle = color;
      ctx.fillText(label, x1 + 3, y1 - 4);
    }
  }, [detections, color, width, height]);

  return (
    <canvas
      ref={canvasRef}
      width={width}
      height={height}
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        pointerEvents: 'none',
        zIndex: 2,
      }}
    />
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

  // Rotated image: 90° counter-clockwise
  const rotatedImgStyle: React.CSSProperties = {
    width: '100%',
    height: '100%',
    objectFit: 'cover',
    transform: 'rotate(-90deg)',
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
        width: '100%',
        aspectRatio: '4 / 3',
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
              <img src={cameraUrl} alt={`${robotId} rgb`} style={rotatedImgStyle} />
              {/* YOLO detection overlay (also rotated) */}
              <div style={{
                position: 'absolute', top: 0, left: 0, width: '100%', height: '100%',
                transform: 'rotate(-90deg)',
                transformOrigin: 'center center',
                zIndex: 2,
              }}>
                <DetectionOverlay
                  detections={detections}
                  color={color}
                  width={640}
                  height={480}
                />
              </div>
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
            <img src={depthUrl} alt={`${robotId} depth`} style={rotatedImgStyle} />
          ) : (
            <div style={noFeedStyle}>No depth</div>
          )}
        </div>
      </div>
    </div>
  );
}
