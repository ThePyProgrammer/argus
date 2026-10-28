import { useState, useRef } from 'react';
import { useRobotStore } from '../stores/robotStore';
import CameraFeed from './CameraFeed';

export default function CameraStrip() {
  const [collapsed, setCollapsed] = useState(false);
  const prevRef = useRef<string[]>([]);
  const robotIds = useRobotStore((s) => {
    const next = [...s.robots.keys()];
    const prev = prevRef.current;
    if (prev.length === next.length && prev.every((id, i) => id === next[i])) {
      return prev;
    }
    prevRef.current = next;
    return next;
  });

  return (
    <div
      className="camera-strip"
      style={{
        background: 'var(--surface)',
        borderTop: '1px solid var(--line)',
        height: collapsed ? '28px' : '188px',
        overflow: 'hidden',
        transition: 'height 0.2s ease',
      }}
    >
      <button className="camera-strip-header" onClick={() => setCollapsed(!collapsed)} aria-expanded={!collapsed}>
        <span>Sensor feeds <span style={{ marginLeft: 8, color: 'var(--muted)', fontWeight: 400 }}>{robotIds.length.toString().padStart(2, '0')}</span></span>
        <span>{collapsed ? 'Expand feeds +' : 'RGB & depth / Collapse -'}</span>
      </button>
      {/* Feed row */}
      {!collapsed && (
        <div
          style={{
            display: 'flex',
            gap: '8px',
            padding: '0 6px 6px',
            overflowX: 'auto',
            overflowY: 'hidden',
            height: '160px',
          }}
        >
          {robotIds.map((id) => (
            <CameraFeed key={id} robotId={id} />
          ))}
          {robotIds.length === 0 && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: '100%',
                color: 'var(--muted)',
                fontSize: '13px',
              }}
            >
              No robots connected
            </div>
          )}
        </div>
      )}
    </div>
  );
}
