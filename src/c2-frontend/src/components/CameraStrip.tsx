import { useState } from 'react';
import { useRobotStore } from '../stores/robotStore';
import CameraFeed from './CameraFeed';

export default function CameraStrip() {
  const [collapsed, setCollapsed] = useState(false);
  const robotIds = useRobotStore((s) => [...s.robots.keys()]);

  return (
    <div
      style={{
        background: '#111122',
        borderTop: '1px solid #2a2a4a',
        height: collapsed ? '32px' : '272px',
        overflow: 'hidden',
        transition: 'height 0.2s ease',
      }}
    >
      {/* Toggle bar */}
      <div
        onClick={() => setCollapsed(!collapsed)}
        style={{
          height: '32px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: 'pointer',
          fontSize: '12px',
          color: '#888',
          userSelect: 'none',
        }}
      >
        {collapsed ? '\u25B2 Camera Feeds' : '\u25BC Camera Feeds'}
      </div>
      {/* Feed row */}
      {!collapsed && (
        <div
          style={{
            display: 'flex',
            gap: '8px',
            padding: '0 8px 8px 8px',
            overflowX: 'auto',
            height: '240px',
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
                color: '#555',
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
