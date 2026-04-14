import { useState } from 'react';
import { useControlStore } from '../stores/controlStore';
import { useRobotStore } from '../stores/robotStore';
import { useMetricsStore } from '../stores/metricsStore';
import AlgorithmSection from './AlgorithmSection';
import DetectorSection from './DetectorSection';
import SliderField from './SliderField';

export default function ControlPanel() {
  const [showCloudConfig, setShowCloudConfig] = useState(false);
  const [showCloudOffset, setShowCloudOffset] = useState(false);
  const [showRestart, setShowRestart] = useState(false);
  const [spawnA, setSpawnA] = useState({ x: -2.0, y: 3.0 });
  const [spawnB, setSpawnB] = useState({ x: 5.0, y: -7.0 });
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
  const sceneColored = useControlStore((s) => s.sceneColored);
  const toggleSceneColored = useControlStore((s) => s.toggleSceneColored);
  const colorMode = useRobotStore((s) => s.colorMode);
  const outputMode = useMetricsStore((s) => s.outputMode);
  const setOutputMode = useMetricsStore((s) => s.setOutputMode);

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

  const handleSpeedChange = (speed: number) => {
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
        <SliderField min={0.1} max={5.0} step={0.1} value={simSpeed} onChange={handleSpeedChange} showInput={false} />
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
        {showScene && (
          <button
            onClick={toggleSceneColored}
            style={{
              ...buttonStyle,
              width: '100%',
              background: sceneColored ? '#1b5e20' : '#37474f',
              color: '#e0e0e0',
              border: '1px solid #444',
            }}
          >
            {sceneColored ? 'Grey Scene' : 'Colored Scene'}
          </button>
        )}
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

      {/* RENDERING section - output format toggle */}
      <div style={{ marginTop: '12px', borderTop: '1px solid #2a2a4a', paddingTop: '10px' }}>
        <div style={{ fontSize: '12px', fontWeight: 600, marginBottom: '8px', color: '#888' }}>
          RENDERING
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          {(['cloud', 'voxel', 'mesh'] as const).map((mode) => {
            const labels: Record<string, string> = { cloud: 'Point Cloud', voxel: 'Voxel Grid', mesh: 'Mesh' };
            const isActive = outputMode === mode;
            return (
              <button
                key={mode}
                onClick={() => setOutputMode(mode)}
                aria-pressed={isActive}
                style={{
                  ...buttonStyle,
                  flex: 1,
                  background: isActive ? '#1a3a2a' : '#263238',
                  color: isActive ? '#2ecc71' : '#666',
                  border: isActive ? '2px solid #2ecc71' : '1px solid #444',
                  fontSize: '11px',
                  padding: '6px 4px',
                }}
              >
                {labels[mode]}
              </button>
            );
          })}
        </div>
      </div>

      <AlgorithmSection />

      <DetectorSection />

      {/* Restart section */}
      <div style={{ marginTop: '12px', borderTop: '1px solid #2a2a4a', paddingTop: '10px' }}>
        <div style={{ display: 'flex', gap: '6px', marginBottom: '6px' }}>
          <button
            onClick={() => {
              sendRaw?.({ type: 'command', payload: { action: 'restart' } });
              useRobotStore.getState().setCloudFull([], []);
            }}
            style={{
              ...buttonStyle,
              flex: 2,
              background: '#b71c1c',
              color: '#fff',
              border: 'none',
            }}
          >
            🔄 Restart (Random)
          </button>
          <button
            onClick={() => setShowRestart(!showRestart)}
            style={{
              ...buttonStyle,
              flex: 1,
              background: '#37474f',
              color: '#aaa',
              border: '1px solid #555',
              fontSize: '11px',
            }}
          >
            {showRestart ? 'Hide' : 'Custom'}
          </button>
        </div>
        {showRestart && (
          <div style={{ background: '#12122a', padding: '8px', borderRadius: '4px' }}>
            <div style={{ fontSize: '10px', color: '#666', marginBottom: '6px' }}>
              Set custom spawn positions (X, Y in meters)
            </div>
            {[
              { label: 'Robot A', pos: spawnA, setPos: setSpawnA, color: '#4285f4' },
              { label: 'Robot B', pos: spawnB, setPos: setSpawnB, color: '#ff9800' },
            ].map(({ label, pos, setPos, color }) => (
              <div key={label} style={{ marginBottom: '6px' }}>
                <div style={{ fontSize: '11px', fontWeight: 600, color, marginBottom: '2px' }}>
                  {label}
                </div>
                <div style={{ display: 'flex', gap: '4px' }}>
                  {(['x', 'y'] as const).map((axis) => (
                    <div key={axis} style={{ flex: 1 }}>
                      <div style={{ fontSize: '10px', color: '#777' }}>{axis.toUpperCase()}</div>
                      <input
                        type="number"
                        step="0.5"
                        value={pos[axis]}
                        onChange={(e) => setPos({ ...pos, [axis]: parseFloat(e.target.value) || 0 })}
                        style={{
                          width: '100%', padding: '3px 5px', fontSize: '11px',
                          background: '#1a1a2e', color: '#e0e0e0', border: '1px solid #444',
                          borderRadius: '3px',
                        }}
                      />
                    </div>
                  ))}
                </div>
              </div>
            ))}
            <button
              onClick={() => {
                sendRaw?.({
                  type: 'command',
                  payload: {
                    action: 'restart',
                    positions: {
                      robot_a: [spawnA.x, spawnA.y, 0.3],
                      robot_b: [spawnB.x, spawnB.y, 0.3],
                    },
                  },
                });
                useRobotStore.getState().setCloudFull([], []);
              }}
              style={{
                ...buttonStyle,
                width: '100%',
                background: '#e65100',
                color: '#fff',
                border: 'none',
                fontSize: '12px',
              }}
            >
              Restart at Custom Positions
            </button>
          </div>
        )}
      </div>

      {Object.keys(cloudConfigs).length > 0 && (
        <div style={{ marginTop: '12px', borderTop: '1px solid #2a2a4a', paddingTop: '10px' }}>
          <div
            onClick={() => setShowCloudConfig(!showCloudConfig)}
            style={{
              fontSize: '12px', fontWeight: 600, color: '#888', cursor: 'pointer',
              userSelect: 'none', display: 'flex', justifyContent: 'space-between',
            }}
          >
            <span>CLOUD CONFIG</span>
            <span style={{ fontSize: '10px' }}>{showCloudConfig ? '▼' : '▶'}</span>
          </div>
          {showCloudConfig && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '3px', maxHeight: '200px', overflowY: 'auto', marginTop: '6px' }}>
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
          )}

          <div style={{ marginTop: '10px', borderTop: '1px solid #2a2a4a', paddingTop: '8px' }}>
            <div
              onClick={() => setShowCloudOffset(!showCloudOffset)}
              style={{
                fontSize: '11px', fontWeight: 600, color: '#777', cursor: 'pointer',
                userSelect: 'none', display: 'flex', justifyContent: 'space-between',
              }}
            >
              <span>CLOUD OFFSET</span>
              <span style={{ fontSize: '10px' }}>{showCloudOffset ? '▼' : '▶'}</span>
            </div>
            {showCloudOffset && (
              <div style={{ marginTop: '4px' }}>
                {(['X', 'Y', 'Z'] as const).map((axis, i) => (
                  <div key={axis} style={{ marginBottom: '4px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: '#888' }}>
                      <span>{axis}</span>
                      <span>{cloudOffset[i].toFixed(1)}m</span>
                    </div>
                    <SliderField
                      min={-10} max={10} step={0.1}
                      value={cloudOffset[i]}
                      onChange={(val) => {
                        const newOffset: [number, number, number] = [...cloudOffset];
                        newOffset[i] = val;
                        setCloudOffset(newOffset);
                      }}
                      showInput={false}
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
            )}
          </div>
        </div>
      )}
    </div>
  );
}
