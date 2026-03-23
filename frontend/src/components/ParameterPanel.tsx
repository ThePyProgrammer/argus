import { useSlamStore } from '../stores/slamStore';
import { useControlStore } from '../stores/controlStore';
import { debounce } from '../utils/debounce';

const debouncedSendParam = debounce((key: unknown, value: unknown) => {
  const sendRaw = useControlStore.getState().sendRaw;
  sendRaw?.({ type: 'slam_param_update', param: key, value });
}, 200);

function humanize(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function handleParamChange(key: string, value: unknown, liveTunable?: boolean) {
  const store = useSlamStore.getState();
  store.updateActiveParam(key, value);
  if (liveTunable) {
    debouncedSendParam(key, value);
  } else {
    store.stageParam(key, value);
  }
}

export function ParameterPanel() {
  const backends = useSlamStore((s) => s.backends);
  const activeBackend = useSlamStore((s) => s.activeBackend);
  const activeParameters = useSlamStore((s) => s.activeParameters);

  const backend = backends.find((b) => b.name === activeBackend);
  const properties = backend?.parameter_schema?.properties;

  if (!properties || Object.keys(properties).length === 0) {
    return (
      <div style={{ fontSize: '11px', fontWeight: 400, color: '#666', marginTop: '8px' }}>
        No tunable parameters
      </div>
    );
  }

  return (
    <div style={{ marginTop: '8px' }}>
      {Object.entries(properties).map(([key, prop]) => {
        const currentValue = activeParameters[key] ?? prop.default ?? (prop.type === 'boolean' ? false : (prop.minimum ?? 0));

        return (
          <div key={key} style={{ marginBottom: '8px' }}>
            {/* Label row */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              {prop.live_tunable === true ? (
                <span style={{ color: '#ff9800', fontSize: '12px' }} title="Changes apply live">
                  {'\u26A1'}
                </span>
              ) : (
                <span style={{ color: '#888', fontSize: '12px' }} title="Requires restart">
                  {'\uD83D\uDD12'}
                </span>
              )}
              <span style={{ fontSize: '11px', fontWeight: 600, color: '#aaa' }}>
                {humanize(key)}
              </span>
            </div>

            {/* Description */}
            {prop.description && (
              <div style={{ fontSize: '10px', color: '#666', marginBottom: '4px' }}>
                {prop.description}
              </div>
            )}

            {/* Numeric control */}
            {(prop.type === 'number' || prop.type === 'integer') && (
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <input
                  type="range"
                  min={prop.minimum}
                  max={prop.maximum}
                  step={prop.type === 'integer' ? 1 : ((prop.maximum ?? 1) - (prop.minimum ?? 0)) / 100}
                  value={currentValue as number}
                  onChange={(e) => {
                    handleParamChange(key, parseFloat(e.target.value), prop.live_tunable);
                  }}
                  style={{ flex: 1 }}
                />
                <input
                  type="number"
                  min={prop.minimum}
                  max={prop.maximum}
                  step={prop.type === 'integer' ? 1 : 0.001}
                  value={currentValue as number}
                  onChange={(e) => {
                    const parsed = parseFloat(e.target.value);
                    if (isNaN(parsed)) return;
                    const min = prop.minimum ?? -Infinity;
                    const max = prop.maximum ?? Infinity;
                    const clamped = Math.min(Math.max(parsed, min), max);
                    handleParamChange(key, clamped, prop.live_tunable);
                  }}
                  style={{
                    width: '64px',
                    background: '#1a1a2e',
                    color: '#e0e0e0',
                    border: '1px solid #444',
                    borderRadius: '3px',
                    padding: '3px 5px',
                    fontSize: '11px',
                  }}
                />
              </div>
            )}

            {/* Boolean control */}
            {prop.type === 'boolean' && (
              <button
                onClick={() => handleParamChange(key, !(currentValue as boolean), prop.live_tunable)}
                style={{
                  width: '100%',
                  padding: '4px 8px',
                  background: currentValue ? '#1b5e20' : '#37474f',
                  color: '#e0e0e0',
                  border: '1px solid #444',
                  fontSize: '11px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  borderRadius: '3px',
                }}
              >
                {currentValue ? 'On' : 'Off'}
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}
