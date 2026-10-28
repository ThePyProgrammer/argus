import { useLayoutEffect, useRef, useState } from 'react';
import { useRobotStore, type Detection3DItem } from '../stores/robotStore';
import { robotColor, OKABE_ITO_RGB } from '../utils/palette';
import { cameraOverlayRect } from '../utils/cameraOverlay';

interface CameraFeedProps {
  robotId: string;
}

/**
 * Interactive YOLO detection overlays as positioned HTML divs.
 * Hover to highlight and see a tooltip with details.
 */
function DetectionOverlay({
  items,
  color: _color,
  imgWidth,
  imgHeight,
}: {
  items: Detection3DItem[];
  color: string;
  imgWidth: number;
  imgHeight: number;
}) {
  const [hovered, setHovered] = useState<number | null>(null);
  const overlayRef = useRef<HTMLDivElement>(null);
  const [viewport, setViewport] = useState({ width: imgWidth, height: imgHeight });

  useLayoutEffect(() => {
    const element = overlayRef.current;
    if (!element) return;
    const update = () => {
      const { width, height } = element.getBoundingClientRect();
      if (width > 0 && height > 0) setViewport({ width, height });
    };
    update();
    const observer = new ResizeObserver(update);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={overlayRef} style={{
      position: 'absolute', top: 0, left: 0, width: '100%', height: '100%',
      zIndex: 2,
    }}>
      {items.map((det, i) => {
        // Graceful degradation: skip items without a 2D bbox (bbox_xyxy is optional per Plan 01).
        if (!det.bbox_xyxy || det.bbox_xyxy.length < 4) return null;
        const [x1, y1, x2, y2] = det.bbox_xyxy;

        // D-16 (DET-UI-05): per-class color via OKABE_ITO_RGB indexed by class_id modulo palette length.
        // Guard against undefined/negative class_id (T-03-23); COCO indices are non-negative but defensive anyway.
        const [cr, cg, cb] = OKABE_ITO_RGB[(det.class_id ?? 0) >= 0
          ? (det.class_id ?? 0) % OKABE_ITO_RGB.length
          : 0];
        const classColor = `rgb(${cr}, ${cg}, ${cb})`;

        const { left, top, width, height } = cameraOverlayRect(
          [x1, y1, x2, y2], imgWidth, imgHeight, viewport.width, viewport.height,
        );
        const isHovered = hovered === i;

        // Determine if label/tooltip would clip at top/bottom
        const pctTop = (top / viewport.height) * 100;
        const pctBottom = ((viewport.height - top - height) / viewport.height) * 100;
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
              border: `2px solid ${isHovered ? '#fff' : classColor}`,
              borderRadius: '2px',
              background: isHovered ? 'rgba(255,255,255,0.15)' : 'rgba(255,255,255,0.05)',
              cursor: 'pointer',
              transition: 'all 0.15s ease',
              boxShadow: isHovered ? `0 0 8px ${classColor}` : 'none',
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
              background: isHovered ? classColor : 'rgba(0,0,0,0.75)',
              color: isHovered ? '#000' : classColor,
              fontSize: '10px',
              fontWeight: 700,
              fontFamily: 'monospace',
              whiteSpace: 'nowrap',
              borderRadius: '2px',
              transition: 'all 0.15s ease',
              textShadow: isHovered ? 'none' : '0 1px 2px rgba(0,0,0,0.9)',
            }}>
              {det.class_name} {(det.score * 100).toFixed(0)}%
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
                border: `1px solid ${classColor}`,
                borderRadius: '4px',
                fontSize: '11px',
                fontFamily: 'monospace',
                color: '#eee',
                whiteSpace: 'nowrap',
                zIndex: 10,
                pointerEvents: 'none',
              }}>
                <div><strong style={{ color: classColor }}>{det.class_name}</strong></div>
                <div>Score: {(det.score * 100).toFixed(2)}%</div>
                <div>BBox: [{det.bbox_xyxy.map(v => v.toFixed(0)).join(', ')}]</div>
                <div>3D: [{det.center.map(v => v.toFixed(2)).join(', ')}]</div>
                {det.track_id !== undefined && (
                  <div>Track: #{det.track_id}</div>
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
  const detections = useRobotStore(
    (s) => s.robots.get(robotId)?.detections_3d,
  );
  const detectionItems = detections?.items ?? [];
  const [imageHeight, imageWidth] = detections?.image_hw ?? [240, 320];
  const colorIndex = useRobotStore(
    (s) => s.robots.get(robotId)?.colorIndex ?? 0,
  );
  const color = robotColor(colorIndex);

  // The server sends the raw image orientation; overlays use its pixel frame.
  const imgStyle: React.CSSProperties = {
    width: '100%',
    height: '100%',
    objectFit: 'contain',
    display: 'block',
  };

  const noFeedStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100%',
    color: 'var(--muted)',
    fontSize: '12px',
  };

  return (
    <div
      className="camera-feed"
      style={{
        width: '393px',
        height: '150px',
        flexShrink: 0,
        background: 'var(--canvas)',
        borderRadius: '4px',
        overflow: 'hidden',
        position: 'relative',
      }}
    >
      {/* Color accent bar */}
      <div style={{ height: '3px', background: color, width: '100%' }} />
      {/* Label */}
      <div className="camera-caption"
        style={{
          position: 'absolute',
          top: '6px',
          left: '8px',
          fontSize: '11px',
          fontWeight: 600,
          background: 'rgba(0,0,0,0.6)',
          padding: '2px 6px',
          borderRadius: '3px',
          color: 'var(--ink)',
          zIndex: 3,
        }}
      >
        {robotId}
      </div>
      {/* Side-by-side: RGB (with detection overlay) + Depth */}
      <div style={{ display: 'flex', height: 'calc(100% - 3px)' }}>
        <div style={{ flex: 1, minWidth: 0, position: 'relative', overflow: 'hidden' }}>
          <div className="camera-caption" style={{
            position: 'absolute', bottom: '4px', left: '4px',
            fontSize: '10px', color: 'var(--muted)', background: 'rgba(0,0,0,0.5)',
            padding: '1px 4px', borderRadius: '2px', zIndex: 3,
          }}>RGB</div>
          {cameraUrl ? (
            <>
              <img src={cameraUrl} alt={`${robotId} rgb`} style={imgStyle} />
              {/* YOLO detection overlay (interactive) */}
              <DetectionOverlay
                items={detectionItems}
                color={color}
                imgWidth={imageWidth}
                imgHeight={imageHeight}
              />
            </>
          ) : (
            <div className="camera-empty" style={noFeedStyle}>No RGB</div>
          )}
        </div>
        <div style={{ width: '1px', background: 'var(--line)' }} />
        <div style={{ flex: 1, minWidth: 0, position: 'relative', overflow: 'hidden' }}>
          <div className="camera-caption" style={{
            position: 'absolute', bottom: '4px', left: '4px',
            fontSize: '10px', color: 'var(--muted)', background: 'rgba(0,0,0,0.5)',
            padding: '1px 4px', borderRadius: '2px', zIndex: 3,
          }}>Depth</div>
          {depthUrl ? (
            <img src={depthUrl} alt={`${robotId} depth`} style={imgStyle} />
          ) : (
            <div className="camera-empty" style={noFeedStyle}>No depth</div>
          )}
        </div>
      </div>
    </div>
  );
}
