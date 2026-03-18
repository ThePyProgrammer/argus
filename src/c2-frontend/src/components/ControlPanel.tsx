import { useControlStore } from '../stores/controlStore';

export default function ControlPanel() {
  const isRunning = useControlStore((s) => s.isRunning);
  const isPaused = useControlStore((s) => s.isPaused);
  const simSpeed = useControlStore((s) => s.simSpeed);
  const sendCommand = useControlStore((s) => s.sendCommand);
  const setRunning = useControlStore((s) => s.setRunning);
  const setPaused = useControlStore((s) => s.setPaused);
  const setSimSpeed = useControlStore((s) => s.setSimSpeed);

  const handleStartStop = () => {
    const action = isRunning ? 'stop' : 'start';
    sendCommand?.({ action });
    setRunning(!isRunning);
    if (!isRunning) {
      setPaused(false);
    }
  };

  const handlePauseResume = () => {
    const action = isPaused ? 'resume' : 'pause';
    sendCommand?.({ action });
    setPaused(!isPaused);
  };

  const handleSpeedChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const speed = parseFloat(e.target.value);
    setSimSpeed(speed);
    sendCommand?.({ action: 'set_speed', value: speed });
  };

  const buttonStyle: React.CSSProperties = {
    padding: '8px 16px',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    fontWeight: 600,
    fontSize: '13px',
    flex: 1,
  };

  return (
    <div
      style={{
        padding: '12px',
        background: '#1a1a3e',
        borderTop: '1px solid #2a2a4a',
      }}
    >
      <div style={{ fontSize: '12px', fontWeight: 600, marginBottom: '8px', color: '#888' }}>
        CONTROLS
      </div>
      <div style={{ display: 'flex', gap: '8px', marginBottom: '10px' }}>
        <button
          onClick={handleStartStop}
          style={{
            ...buttonStyle,
            background: isRunning ? '#d32f2f' : '#2e7d32',
            color: '#fff',
          }}
        >
          {isRunning ? 'Stop' : 'Start'}
        </button>
        <button
          onClick={handlePauseResume}
          disabled={!isRunning}
          style={{
            ...buttonStyle,
            background: isPaused ? '#f57c00' : '#1565c0',
            color: '#fff',
            opacity: isRunning ? 1 : 0.4,
          }}
        >
          {isPaused ? 'Resume' : 'Pause'}
        </button>
      </div>
      <div>
        <label
          style={{ fontSize: '12px', color: '#888', display: 'block', marginBottom: '4px' }}
        >
          Speed: {simSpeed.toFixed(1)}x
        </label>
        <input
          type="range"
          min="0.1"
          max="5.0"
          step="0.1"
          value={simSpeed}
          onChange={handleSpeedChange}
          style={{ width: '100%' }}
        />
      </div>
    </div>
  );
}
