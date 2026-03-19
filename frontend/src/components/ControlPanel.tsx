import { useControlStore } from '../stores/controlStore';
import { useRobotStore } from '../stores/robotStore';

export default function ControlPanel() {
  const isRunning = useControlStore((s) => s.isRunning);
  const isPaused = useControlStore((s) => s.isPaused);
  const simSpeed = useControlStore((s) => s.simSpeed);
  const sendCommand = useControlStore((s) => s.sendCommand);
  const sendRaw = useControlStore((s) => s.sendRaw);
  const setRunning = useControlStore((s) => s.setRunning);
  const setPaused = useControlStore((s) => s.setPaused);
  const setSimSpeed = useControlStore((s) => s.setSimSpeed);
  const cloudConfigs = useControlStore((s) => s.cloudConfigs);
  const activeCloudConfig = useControlStore((s) => s.activeCloudConfig);
  const cloudOffset = useControlStore((s) => s.cloudOffset);
  const setCloudOffset = useControlStore((s) => s.setCloudOffset);
  const showScene = useControlStore((s) => s.showScene);
  const toggleScene = useControlStore((s) => s.toggleScene);
  const colorMode = useRobotStore((s) => s.colorMode);

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

      <div style={{ marginTop: '10px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
        <button
          onClick={toggleScene}
          style={{
            ...buttonStyle,
            width: '100%',
            background: showScene ? '#37474f' : '#263238',
            color: showScene ? '#e0e0e0' : '#666',
            border: '1px solid #444',
          }}
        >
          {showScene ? 'Hide Scene Mesh' : 'Show Scene Mesh'}
        </button>
        <button
          onClick={() => {
            const newMode = colorMode === 'robot_tint' ? 'true_rgb' : 'robot_tint';
            useRobotStore.getState().setColorMode(newMode);
            sendRaw?.({ type: 'set_color_mode', mode: newMode });
          }}
          style={{
            ...buttonStyle,
            width: '100%',
            background: colorMode === 'true_rgb' ? '#1b5e20' : '#37474f',
            color: '#e0e0e0',
            border: '1px solid #444',
          }}
        >
          {colorMode === 'robot_tint' ? 'Switch to True RGB' : 'Switch to Robot Colors'}
        </button>
      </div>

      {Object.keys(cloudConfigs).length > 0 && (
        <div style={{ marginTop: '12px', borderTop: '1px solid #2a2a4a', paddingTop: '10px' }}>
          <div style={{ fontSize: '12px', fontWeight: 600, marginBottom: '6px', color: '#888' }}>
            CLOUD CONFIG
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '3px', maxHeight: '200px', overflowY: 'auto' }}>
            {Object.entries(cloudConfigs).map(([key, label]) => (
              <button
                key={key}
                onClick={() => {
                  sendRaw?.({ type: 'set_cloud_config', config: key });
                }}
                style={{
                  padding: '4px 8px',
                  border: key === activeCloudConfig ? '2px solid #2ecc71' : '1px solid #444',
                  borderRadius: '3px',
                  cursor: 'pointer',
                  fontFamily: 'monospace',
                  fontSize: '11px',
                  textAlign: 'left',
                  background: key === activeCloudConfig ? '#1a3a2a' : '#222',
                  color: key === activeCloudConfig ? '#2ecc71' : '#aaa',
                }}
              >
                <strong>{key}</strong>: {label}
              </button>
            ))}
          </div>

          <div style={{ marginTop: '10px', borderTop: '1px solid #2a2a4a', paddingTop: '8px' }}>
            <div style={{ fontSize: '11px', fontWeight: 600, marginBottom: '4px', color: '#777' }}>
              CLOUD OFFSET
            </div>
            {(['X', 'Y', 'Z'] as const).map((axis, i) => (
              <div key={axis} style={{ marginBottom: '4px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: '#888' }}>
                  <span>{axis}</span>
                  <span>{cloudOffset[i].toFixed(1)}m</span>
                </div>
                <input
                  type="range"
                  min="-10"
                  max="10"
                  step="0.1"
                  value={cloudOffset[i]}
                  onChange={(e) => {
                    const val = parseFloat(e.target.value);
                    const newOffset: [number, number, number] = [...cloudOffset];
                    newOffset[i] = val;
                    setCloudOffset(newOffset);
                  }}
                  style={{ width: '100%', height: '14px' }}
                />
              </div>
            ))}
            <button
              onClick={() => setCloudOffset([0, 0, 0])}
              style={{
                padding: '3px 8px', border: '1px solid #444', borderRadius: '3px',
                cursor: 'pointer', fontSize: '10px', background: '#222', color: '#aaa',
                width: '100%', marginTop: '2px',
              }}
            >
              Reset offsets
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
