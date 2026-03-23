export type ViewMode = '3d' | 'pipeline';

interface ViewToggleProps {
  activeView: ViewMode;
  onViewChange: (view: ViewMode) => void;
}

const containerStyle: React.CSSProperties = {
  position: 'absolute',
  top: 8,
  left: 8,
  zIndex: 10,
  display: 'flex',
  borderRadius: 4,
  overflow: 'hidden',
};

function buttonStyle(active: boolean): React.CSSProperties {
  return {
    height: 32,
    padding: '0 16px',
    fontSize: 13,
    fontWeight: 600,
    border: 'none',
    cursor: 'pointer',
    transition: 'background 0.15s',
    background: active ? '#4fc3f7' : '#2a2a4a',
    color: active ? '#0a0a14' : '#888',
  };
}

export function ViewToggle({ activeView, onViewChange }: ViewToggleProps) {
  return (
    <div style={containerStyle}>
      <button
        style={buttonStyle(activeView === '3d')}
        onClick={() => onViewChange('3d')}
      >
        3D Viewer
      </button>
      <button
        style={buttonStyle(activeView === 'pipeline')}
        onClick={() => onViewChange('pipeline')}
      >
        Pipeline Editor
      </button>
    </div>
  );
}
