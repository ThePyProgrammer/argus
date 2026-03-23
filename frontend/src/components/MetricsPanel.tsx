import { useState } from 'react';
import { useMetricsStore } from '../stores/metricsStore';
import { robotColor } from '../utils/palette';
import Sparkline from './Sparkline';

const STATUS_DOT_COLORS: Record<string, string> = {
  ok: '#2ecc71',
  initializing: '#f1c40f',
  relocalizing: '#f1c40f',
  lost: '#e74c3c',
};

function deltaColor(delta: number): string {
  if (delta === 0) return '#888';
  // For all three metrics (ATE, RPE, ms/frame): lower is better.
  // Negative delta = improvement (green), positive = regression (red).
  return delta < 0 ? '#2ecc71' : '#e74c3c';
}

function formatDelta(current: number, baseline: number): { text: string; color: string } {
  if (baseline === 0) return { text: '0%', color: '#888' };
  const delta = ((current - baseline) / baseline) * 100;
  if (Math.abs(delta) < 0.05) return { text: '0%', color: '#888' };
  const sign = delta > 0 ? '+' : '';
  return {
    text: `${sign}${delta.toFixed(0)}%`,
    color: deltaColor(delta),
  };
}

export default function MetricsPanel() {
  const [collapsed, setCollapsed] = useState(true);
  const perRobot = useMetricsStore((s) => s.perRobot);
  const baseline = useMetricsStore((s) => s.baseline);
  const viewMode = useMetricsStore((s) => s.viewMode);
  const history = useMetricsStore((s) => s.history);
  const setViewMode = useMetricsStore((s) => s.setViewMode);

  const robotIds = Object.keys(perRobot);
  const firstRobotId = robotIds[0] ?? null;

  return (
    <div style={{ background: '#111122', borderTop: '1px solid #2a2a4a' }}>
      {/* Collapse/expand toggle bar */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        style={{
          width: '100%',
          height: '32px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: 'pointer',
          fontSize: '12px',
          fontWeight: 600,
          color: '#888',
          background: 'transparent',
          border: 'none',
          userSelect: 'none',
        }}
      >
        {collapsed ? '\u25B2 Metrics' : '\u25BC Metrics'}
      </button>

      {/* Expanded content */}
      {!collapsed && (
        <div style={{ padding: '12px', paddingTop: 0 }}>
          {/* View mode tabs */}
          <div role="tablist" style={{ display: 'flex', gap: '4px', marginBottom: '12px' }}>
            {(['live', 'baseline'] as const).map((mode) => {
              const isActive = viewMode === mode;
              const label = mode === 'live' ? 'Live' : 'vs Baseline';
              return (
                <button
                  key={mode}
                  role="tab"
                  aria-selected={isActive}
                  onClick={() => setViewMode(mode)}
                  style={{
                    padding: '8px 16px',
                    fontSize: '12px',
                    fontWeight: 600,
                    cursor: 'pointer',
                    background: 'transparent',
                    border: 'none',
                    borderBottom: isActive ? '2px solid #2ecc71' : '2px solid transparent',
                    color: isActive ? '#2ecc71' : '#888',
                  }}
                >
                  {label}
                </button>
              );
            })}
          </div>

          {/* Live view */}
          {viewMode === 'live' && (
            <>
              {robotIds.length === 0 ? (
                <div style={{ padding: '12px 0' }}>
                  <div style={{ fontSize: '13px', color: '#888' }}>No metrics yet</div>
                  <div style={{ fontSize: '11px', color: '#666', marginTop: '4px' }}>
                    Start a session to see live SLAM metrics.
                  </div>
                </div>
              ) : (
                <div style={{ display: 'flex', gap: '24px', overflowX: 'auto' }}>
                  {robotIds.map((robotId, index) => {
                    const m = perRobot[robotId];
                    const dotColor = STATUS_DOT_COLORS[m.tracking_status] ?? '#888';
                    return (
                      <div key={robotId} style={{ minWidth: '140px' }}>
                        {/* Robot header with colored left border */}
                        <div
                          style={{
                            borderLeft: `3px solid ${robotColor(index)}`,
                            paddingLeft: '8px',
                            fontSize: '12px',
                            fontWeight: 600,
                            color: '#e0e0e0',
                            marginBottom: '8px',
                          }}
                        >
                          {robotId}
                        </div>

                        {/* Metric rows */}
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                          {/* ATE */}
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                            <span style={{ fontSize: '12px', color: '#888' }}>ATE</span>
                            <span style={{ fontSize: '13px', fontFamily: 'monospace', color: '#e0e0e0' }}>
                              {m.ate_rmse.toFixed(3)}m
                            </span>
                          </div>

                          {/* RPE */}
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                            <span style={{ fontSize: '12px', color: '#888' }}>RPE</span>
                            <span style={{ fontSize: '13px', fontFamily: 'monospace', color: '#e0e0e0' }}>
                              {m.rpe_rmse.toFixed(3)}m
                            </span>
                          </div>

                          {/* ms/frame */}
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                            <span style={{ fontSize: '12px', color: '#888' }}>ms/frame</span>
                            <span style={{ fontSize: '13px', fontFamily: 'monospace', color: '#e0e0e0' }}>
                              {m.ms_per_frame.toFixed(1)}
                            </span>
                          </div>

                          {/* Status */}
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span style={{ fontSize: '12px', color: '#888' }}>Status</span>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                              <span
                                aria-hidden="true"
                                style={{
                                  width: '8px',
                                  height: '8px',
                                  borderRadius: '50%',
                                  background: dotColor,
                                  display: 'inline-block',
                                }}
                              />
                              <span style={{ fontSize: '13px', color: '#e0e0e0' }}>
                                {m.tracking_status}
                              </span>
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </>
          )}

          {/* Baseline view */}
          {viewMode === 'baseline' && (
            <>
              {baseline === null ? (
                <div style={{ padding: '12px 0' }}>
                  <div style={{ fontSize: '13px', color: '#888' }}>No baseline recorded</div>
                  <div style={{ fontSize: '11px', color: '#666', marginTop: '4px' }}>
                    Run a session with ICP backend first to establish baseline metrics.
                  </div>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {([
                    { key: 'ate_rmse', label: 'ATE', histKey: 'ate_rmse' },
                    { key: 'rpe_rmse', label: 'RPE', histKey: 'rpe_rmse' },
                    { key: 'ms_per_frame', label: 'ms/frm', histKey: 'ms_per_frame' },
                  ] as const).map(({ key, label, histKey }) => {
                    const baselineMetrics = firstRobotId ? baseline[firstRobotId] : null;
                    const currentMetrics = firstRobotId ? perRobot[firstRobotId] : null;
                    const historyData = firstRobotId ? history[firstRobotId] : null;
                    const baselineVal = baselineMetrics ? baselineMetrics[key] : undefined;
                    const currentVal = currentMetrics ? currentMetrics[key] : null;
                    const histArr = historyData ? historyData[histKey] : [];
                    const delta = currentVal != null && baselineVal != null
                      ? formatDelta(currentVal, baselineVal)
                      : { text: '0%', color: '#888' };

                    return (
                      <div
                        key={key}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '12px',
                        }}
                      >
                        <span style={{ fontSize: '12px', color: '#888', minWidth: '50px' }}>
                          {label}
                        </span>
                        <Sparkline
                          data={histArr}
                          width={120}
                          height={30}
                          color="#2ecc71"
                          baselineValue={baselineVal}
                        />
                        <span style={{ fontSize: '13px', fontFamily: 'monospace', color: '#e0e0e0', minWidth: '60px', textAlign: 'right' }}>
                          {currentVal != null
                            ? key === 'ms_per_frame'
                              ? currentVal.toFixed(1)
                              : `${currentVal.toFixed(3)}m`
                            : '--'}
                        </span>
                        <span style={{ fontSize: '11px', color: delta.color, minWidth: '40px', textAlign: 'right' }}>
                          {delta.text}
                        </span>
                      </div>
                    );
                  })}
                  <div style={{ fontSize: '10px', color: '#555', marginTop: '-4px' }}>
                    ICP baseline
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
