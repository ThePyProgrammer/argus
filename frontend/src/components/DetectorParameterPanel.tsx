import { useDetectorStore } from '../stores/detectorStore';
import { useControlStore } from '../stores/controlStore';
import { debounce } from '../utils/debounce';
import SliderField from './SliderField';

const debouncedSendParam = debounce((key: unknown, value: unknown) => {
  const sendRaw = useControlStore.getState().sendRaw;
  sendRaw?.({ type: 'detector_param_update', param: key, value });
}, 200);

function humanize(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function handleParamChange(key: string, value: unknown, liveTunable?: boolean) {
  const store = useDetectorStore.getState();
  store.updateActiveParam(key, value);
  if (liveTunable) {
    debouncedSendParam(key, value);
  } else {
    store.stageParam(key, value);
  }
}

export function DetectorParameterPanel() {
  const backends = useDetectorStore((s) => s.backends);
  const activeBackend = useDetectorStore((s) => s.activeBackend);
  const activeParameters = useDetectorStore((s) => s.activeParameters);

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
              <SliderField
                min={prop.minimum ?? 0}
                max={prop.maximum ?? 1}
                step={prop.type === 'integer' ? 1 : ((prop.maximum ?? 1) - (prop.minimum ?? 0)) / 100}
                value={currentValue as number}
                onChange={(val) => handleParamChange(key, val, prop.live_tunable)}
                isInteger={prop.type === 'integer'}
              />
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
