import { Position } from '@xyflow/react';
import type { NodeProps } from '@xyflow/react';
import { PortHandle } from './PortHandle';
import { usePipelineStore } from '../../stores/pipelineStore';
import type { PipelineNodeData, NodeCategory } from '../../utils/pipelineTypes';

// Category icons (Unicode per UI-SPEC)
const CATEGORY_ICONS: Record<NodeCategory, string> = {
  sensor: '\u{1F4F7}',     // camera
  slam: '\u{1F9ED}',       // compass
  merger: '\u{1F500}',     // shuffle
  filter: '\u2699',        // gear
  splitter: '\u2194',      // left-right arrow
  parameter: '\u{1F522}',  // numbers
  output: '\u{1F4FA}',     // TV
  perception: '\u{1F50D}', // magnifying glass (Phase 7 DET-PIPELINE-01)
};

// Status badge colors
const STATUS_COLORS: Record<string, string> = {
  idle: '#666666',
  processing: '#2ecc71',
  error: '#d32f2f',
  initializing: '#4fc3f7',
};

// Pulsing animation for initializing status via CSS keyframes
const pulseKeyframes = `
@keyframes pipeline-node-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}
`;

// Inject keyframes once
let stylesInjected = false;
function injectStyles() {
  if (stylesInjected || typeof document === 'undefined') return;
  const style = document.createElement('style');
  style.textContent = pulseKeyframes;
  document.head.appendChild(style);
  stylesInjected = true;
}

/**
 * Custom React Flow node component.
 * Renders colored header, typed port handles, inline primary params, and status badge.
 */
function PipelineNodeComponent({ data, selected, id }: NodeProps) {
  injectStyles();

  const nodeData = data as unknown as PipelineNodeData;
  const nodeStatuses = usePipelineStore((s) => s.nodeStatuses);
  const selectNode = usePipelineStore((s) => s.selectNode);

  const status = (nodeStatuses[id] ?? nodeData.status) as string;
  const statusColor = STATUS_COLORS[status] ?? STATUS_COLORS.idle;
  const isInitializing = status === 'initializing';

  // Extract primary params from schema (max 3)
  const primaryParams: Array<{ key: string; schema: Record<string, unknown>; value: unknown }> = [];
  if (nodeData.parameterSchema) {
    const props = (nodeData.parameterSchema as Record<string, unknown>).properties as
      | Record<string, Record<string, unknown>>
      | undefined;
    if (props) {
      for (const [key, schemaProp] of Object.entries(props)) {
        if (schemaProp.primary === true && primaryParams.length < 3) {
          primaryParams.push({ key, schema: schemaProp, value: nodeData.paramValues[key] });
        }
      }
    }
  }

  const handleClick = () => {
    selectNode(id);
  };

  return (
    <div
      onClick={handleClick}
      style={{
        background: selected ? '#242448' : '#1e1e32',
        border: selected ? '2px solid #4fc3f7' : '1px solid #2a2a4a',
        borderRadius: '8px',
        minWidth: '220px',
        maxWidth: '320px',
        position: 'relative',
        cursor: 'pointer',
      }}
    >
      {/* Header bar */}
      <div
        style={{
          background: nodeData.headerColor,
          height: '28px',
          padding: '0 8px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderRadius: '6px 6px 0 0',
        }}
      >
        <span style={{ fontSize: '11px', fontWeight: 600, color: '#ffffff' }}>
          {CATEGORY_ICONS[nodeData.category]} {nodeData.label}
        </span>
        <span
          aria-live="polite"
          aria-label={`Status: ${status}`}
          style={{
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            background: statusColor,
            display: 'inline-block',
            flexShrink: 0,
            animation: isInitializing ? 'pipeline-node-pulse 1.5s ease-in-out infinite' : undefined,
          }}
        />
      </div>

      {/* Node body */}
      <div style={{ padding: '8px', position: 'relative' }}>
        {/* Input ports (left side) */}
        {nodeData.inputs.map((port, i) => (
          <PortHandle
            key={port.id}
            port={port}
            type="target"
            position={Position.Left}
            index={i}
            totalPorts={nodeData.inputs.length}
          />
        ))}

        {/* Spacer for ports */}
        <div style={{ minHeight: `${Math.max(nodeData.inputs.length, nodeData.outputs.length) * 24 + 8}px` }} />

        {/* Inline primary params */}
        {primaryParams.length > 0 && (
          <div style={{ marginTop: '4px' }}>
            {primaryParams.map(({ key, schema, value }) => {
              const liveTunable = schema.live_tunable === true;
              const numValue = typeof value === 'number' ? value : Number(schema.default ?? 0);
              const isBool = schema.type === 'boolean';

              return (
                <div
                  key={key}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    marginBottom: '4px',
                  }}
                >
                  <span style={{ fontSize: '11px', fontWeight: 600, color: '#aaa', minWidth: '60px' }}>
                    {key}
                  </span>
                  <span style={{ fontSize: '10px', color: liveTunable ? '#ff9800' : '#666' }}>
                    {liveTunable ? '\u26A1' : '\u{1F512}'}
                  </span>
                  {isBool ? (
                    <div
                      style={{
                        width: '28px',
                        height: '14px',
                        borderRadius: '7px',
                        background: value ? '#2ecc71' : '#4a4a6a',
                        position: 'relative',
                      }}
                    >
                      <div
                        style={{
                          width: '10px',
                          height: '10px',
                          borderRadius: '50%',
                          background: '#fff',
                          position: 'absolute',
                          top: '2px',
                          left: value ? '16px' : '2px',
                          transition: 'left 0.15s',
                        }}
                      />
                    </div>
                  ) : (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px', flex: 1 }}>
                      <div
                        style={{
                          flex: 1,
                          height: '4px',
                          background: '#4a4a6a',
                          borderRadius: '2px',
                          position: 'relative',
                          minWidth: '60px',
                        }}
                      >
                        <div
                          style={{
                            position: 'absolute',
                            left: 0,
                            top: 0,
                            height: '4px',
                            borderRadius: '2px',
                            background: '#4fc3f7',
                            width: `${Math.min(100, Math.max(0, ((numValue - Number(schema.minimum ?? 0)) / (Number(schema.maximum ?? 1) - Number(schema.minimum ?? 0))) * 100))}%`,
                          }}
                        />
                      </div>
                      <span style={{ fontSize: '10px', color: '#888', minWidth: '30px', textAlign: 'right' }}>
                        {typeof numValue === 'number' ? numValue.toFixed(numValue % 1 === 0 ? 0 : 2) : numValue}
                      </span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* Output ports (right side) */}
        {nodeData.outputs.map((port, i) => (
          <PortHandle
            key={port.id}
            port={port}
            type="source"
            position={Position.Right}
            index={i}
            totalPorts={nodeData.outputs.length}
          />
        ))}
      </div>
    </div>
  );
}

// CRITICAL: nodeTypes defined at MODULE scope (not inside a component) to prevent remount -- Pitfall 1
export const nodeTypes = { pipeline: PipelineNodeComponent };

export { PipelineNodeComponent };
