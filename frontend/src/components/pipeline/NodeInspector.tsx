import { usePipelineStore } from '../../stores/pipelineStore';
import { useControlStore } from '../../stores/controlStore';
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

  const selectedNode = nodes.find((n) => n.id === selectedNodeId);

  const containerStyle: React.CSSProperties = {
    width: 320,
    background: '#1a1a2e',
    borderLeft: '1px solid #2a2a4a',
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
            color: '#666',
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
  const catColor = CATEGORY_COLORS[category] ?? '#666';
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
        <span style={{ fontSize: 14, fontWeight: 600, color: '#e0e0e0' }}>{label}</span>
      </div>
      <div style={{ fontSize: 10, color: '#666', marginTop: 4, marginLeft: 16 }}>
        {selectedNode.data.nodeType}
      </div>

      {/* Registry info */}
      {registryName && (
        <div style={{ fontSize: 10, color: '#888', marginTop: 4, marginLeft: 16 }}>
          Backend: {registryName}
        </div>
      )}

      {/* Separator */}
      <div style={{ borderTop: '1px solid #2a2a4a', margin: '16px 0' }} />

      {/* Parameters heading */}
      <div style={{ fontSize: 14, fontWeight: 600, color: '#e0e0e0', marginBottom: 12 }}>
        Parameters
      </div>

      {/* Parameters */}
      {!properties || Object.keys(properties).length === 0 ? (
        <div style={{ fontSize: 11, color: '#666' }}>No tunable parameters</div>
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
                  <span style={{ color: '#888', fontSize: 12 }} title="Requires restart">
                    {'\uD83D\uDD12'}
                  </span>
                )}
                <span style={{ fontSize: 11, fontWeight: 600, color: '#aaa' }}>
                  {humanize(key)}
                </span>
              </div>

              {/* Description */}
              {typeof prop.description === 'string' && (
                <div style={{ fontSize: 10, color: '#666', marginBottom: 4 }}>
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
                    background: currentValue ? '#1b5e20' : '#37474f',
                    color: '#e0e0e0',
                    border: '1px solid #444',
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
