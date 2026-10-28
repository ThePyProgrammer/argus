import { useState } from 'react';
import { usePipelineStore } from '../../stores/pipelineStore';
import { useControlStore } from '../../stores/controlStore';
import { useDetectorStore } from '../../stores/detectorStore';
import { useRobotStore } from '../../stores/robotStore';
import { robotColor } from '../../utils/palette';
import { CATEGORY_COLORS } from '../../utils/nodeDefinitions';
import { debounce } from '../../utils/debounce';
import SliderField from '../SliderField';

function humanize(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

const debouncedSendPipelineParam = debounce((nodeId: unknown, key: unknown, value: unknown) => {
  const sendRaw = useControlStore.getState().sendRaw;
  sendRaw?.({ type: 'pipeline_param_update', nodeId, param: key, value });
}, 200);

export function NodeInspector() {
  const selectedNodeId = usePipelineStore((s) => s.selectedNodeId);
  const nodes = usePipelineStore((s) => s.nodes);
  // Phase 7 D-02 — backend hot-swap dropdown reads catalog from the store.
  const availableRegistryNodes = usePipelineStore((s) => s.availableRegistryNodes);
  // Phase 8 DET-STRETCH-04 — per-robot backend override
  const robots = useRobotStore((s) => s.robots);
  const perRobotBackend = useDetectorStore((s) => s.perRobotBackend);
  const [perRobotError, setPerRobotError] = useState<Record<string, string>>({});

  const selectedNode = nodes.find((n) => n.id === selectedNodeId);

  const containerStyle: React.CSSProperties = {
    width: 320,
    background: 'var(--surface)',
    borderLeft: '1px solid var(--line)',
    height: '100%',
    overflowY: 'auto',
    padding: 16,
    boxSizing: 'border-box',
  };

  if (!selectedNode) {
    return (
      <div style={containerStyle}>
        <div
          style={{
            fontSize: 13,
            color: 'var(--muted)',
            textAlign: 'center',
            marginTop: 64,
          }}
        >
          Select a node to view its parameters
        </div>
      </div>
    );
  }

  const { category, label, registryName, parameterSchema, paramValues } = selectedNode.data;
  const catColor = CATEGORY_COLORS[category] ?? 'var(--muted)';
  const properties = (parameterSchema as Record<string, unknown> | null)?.properties as
    | Record<string, Record<string, unknown>>
    | undefined;

  function handleParamChange(key: string, value: unknown, liveTunable?: boolean) {
    if (!selectedNodeId) return;
    usePipelineStore.getState().updateNodeParam(selectedNodeId, key, value);
    if (liveTunable) {
      debouncedSendPipelineParam(selectedNodeId, key, value);
    }
  }

  return (
    <div style={containerStyle}>
      {/* Title section */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div
          style={{
            width: 8,
            height: 8,
            borderRadius: '50%',
            background: catColor,
            flexShrink: 0,
          }}
        />
        <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--ink)' }}>{label}</span>
      </div>
      <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 4, marginLeft: 16 }}>
        {selectedNode.data.nodeType}
      </div>

      {/* Registry info */}
      {registryName && (
        <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 4, marginLeft: 16 }}>
          Backend: {registryName}
        </div>
      )}

      {/* Phase 7 D-02 — backend hot-swap dropdown for perception nodes */}
      {selectedNode.data.nodeType &&
        ['detector_generic', 'detection3d_generic', 'tracker_generic'].includes(
          selectedNode.data.nodeType,
        ) && (
          <select
            aria-label="Backend"
            value={registryName ?? ''}
            onChange={(e) => {
              if (!selectedNodeId) return;
              usePipelineStore
                .getState()
                .updateNodeParam(selectedNodeId, 'backend', e.target.value);
            }}
            style={{
              width: '100%',
              marginTop: 4,
              marginLeft: 16,
              padding: '4px 8px',
              background: 'var(--surface-inset)',
              color: 'var(--ink)',
              border: '1px solid var(--line)',
              borderRadius: 3,
              fontSize: 11,
              fontWeight: 600,
              boxSizing: 'border-box',
            }}
          >
            {(() => {
              const baseKind = selectedNode.data.nodeType.replace(/_generic$/, '');
              return availableRegistryNodes
                .filter(
                  (rn) =>
                    rn.category === 'perception' && rn.type.startsWith(`${baseKind}_`),
                )
                .map((rn) => (
                  <option key={rn.type} value={rn.registryName}>
                    {rn.label}
                  </option>
                ));
            })()}
          </select>
        )}

      {/* Phase 8 DET-STRETCH-04 — per-robot backend override section */}
      {selectedNode.data.nodeType === 'detector_generic' && robots.size > 1 && (
        <div>
          <div style={{ borderTop: '1px solid var(--line)', margin: '12px 0 8px 0' }} />
          <div style={{
            fontSize: 10,
            fontWeight: 600,
            letterSpacing: '1px',
            textTransform: 'uppercase',
            color: 'var(--muted)',
            marginBottom: 8,
          }}>
            per-robot override
          </div>
          {[...robots.entries()].map(([rid, _robot], index) => (
            <div key={rid} style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              marginBottom: 8,
              borderLeft: `3px solid ${robotColor(index)}`,
              paddingLeft: 8,
            }}>
              <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--muted)', minWidth: 60 }}>
                Robot {index}
              </span>
              <select
                aria-label={`Backend for ${rid}`}
                value={perRobotBackend[rid] ?? registryName ?? ''}
                onChange={async (e) => {
                  const newBackend = e.target.value;
                  try {
                    setPerRobotError((prev) => {
                      const next = { ...prev };
                      delete next[rid];
                      return next;
                    });
                    const res = await fetch(
                      `/api/detectors/select?robot_id=${encodeURIComponent(rid)}`,
                      {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ backend: newBackend }),
                      },
                    );
                    if (res.ok) {
                      useDetectorStore.getState().setPerRobotBackend(rid, newBackend);
                    } else {
                      const detail = await res.text();
                      setPerRobotError((prev) => ({
                        ...prev,
                        [rid]: `Backend swap failed for ${rid}: ${detail}`,
                      }));
                    }
                  } catch (err) {
                    setPerRobotError((prev) => ({
                      ...prev,
                      [rid]: `Backend swap failed for ${rid}: ${err instanceof Error ? err.message : 'unknown error'}`,
                    }));
                  }
                }}
                style={{
                  flex: 1,
                  padding: '4px 8px',
                  background: 'var(--surface-inset)',
                  color: 'var(--ink)',
                  border: '1px solid var(--line)',
                  borderRadius: 3,
                  fontSize: 11,
                  fontWeight: 600,
                }}
              >
                {(() => {
                  const baseKind = selectedNode.data.nodeType!.replace(/_generic$/, '');
                  return availableRegistryNodes
                    .filter(
                      (rn) =>
                        rn.category === 'perception' && rn.type.startsWith(`${baseKind}_`),
                    )
                    .map((rn) => (
                      <option key={rn.type} value={rn.registryName}>
                        {rn.label}
                      </option>
                    ));
                })()}
              </select>
              {perRobotError[rid] && (
                <div style={{ fontSize: 11, color: 'var(--danger)', marginTop: 4, marginLeft: 16 }}>
                  {perRobotError[rid]}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Separator */}
      <div style={{ borderTop: '1px solid var(--line)', margin: '16px 0' }} />

      {/* Parameters heading */}
      <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--ink)', marginBottom: 12 }}>
        Parameters
      </div>

      {/* Parameters */}
      {!properties || Object.keys(properties).length === 0 ? (
        <div style={{ fontSize: 11, color: 'var(--muted)' }}>No tunable parameters</div>
      ) : (
        Object.entries(properties).map(([key, prop]) => {
          const currentValue =
            paramValues[key] ??
            prop.default ??
            (prop.type === 'boolean' ? false : ((prop.minimum as number) ?? 0));

          return (
            <div key={key} style={{ marginBottom: 8 }}>
              {/* Label row */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                {prop.live_tunable === true ? (
                  <span style={{ color: '#ff9800', fontSize: 12 }} title="Changes apply live">
                    {'\u26A1'}
                  </span>
                ) : (
                  <span style={{ color: 'var(--muted)', fontSize: 12 }} title="Requires restart">
                    {'\uD83D\uDD12'}
                  </span>
                )}
                <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--muted)' }}>
                  {humanize(key)}
                </span>
              </div>

              {/* Description */}
              {typeof prop.description === 'string' && (
                <div style={{ fontSize: 10, color: 'var(--muted)', marginBottom: 4 }}>
                  {prop.description}
                </div>
              )}

              {/* Numeric control */}
              {(prop.type === 'number' || prop.type === 'integer') && (
                <SliderField
                  min={(prop.minimum as number) ?? 0}
                  max={(prop.maximum as number) ?? 1}
                  step={prop.type === 'integer' ? 1 : (((prop.maximum as number) ?? 1) - ((prop.minimum as number) ?? 0)) / 100}
                  value={currentValue as number}
                  onChange={(val) => handleParamChange(key, val, !!prop.live_tunable)}
                  isInteger={prop.type === 'integer'}
                />
              )}

              {/* Boolean control */}
              {prop.type === 'boolean' && (
                <button
                  onClick={() =>
                    handleParamChange(key, !(currentValue as boolean), !!prop.live_tunable)
                  }
                  style={{
                    width: '100%',
                    padding: '4px 8px',
                    background: currentValue ? 'var(--accent-wash)' : 'var(--surface-inset)',
                    color: 'var(--ink)',
                    border: '1px solid var(--line-strong)',
                    fontSize: 11,
                    fontWeight: 600,
                    cursor: 'pointer',
                    borderRadius: 3,
                  }}
                >
                  {currentValue ? 'On' : 'Off'}
                </button>
              )}
            </div>
          );
        })
      )}
    </div>
  );
}
