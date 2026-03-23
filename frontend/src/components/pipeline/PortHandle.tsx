import { Handle, Position } from '@xyflow/react';
import type { PortDef } from '../../utils/pipelineTypes';
import { PORT_COLORS, PORT_SHAPES } from '../../utils/nodeDefinitions';

interface PortHandleProps {
  port: PortDef;
  type: 'source' | 'target';
  position: Position;
  index: number;
  totalPorts: number;
}

/**
 * Custom React Flow Handle with typed socket visuals.
 * Colors and shapes per data type (see UI-SPEC port data type table).
 */
export function PortHandle({ port, type, position, index }: PortHandleProps) {
  const color = PORT_COLORS[port.dataType];
  const shape = PORT_SHAPES[port.dataType];

  const isDiamond = shape === 'diamond';
  const isSquare = shape === 'square';

  const size = isDiamond ? 10 : 12;
  const borderRadius = isDiamond ? '2px' : isSquare ? '2px' : '50%';
  const transform = isDiamond ? 'rotate(45deg)' : undefined;

  // Header 28px + 8px body padding + index * 24px port spacing (UI-SPEC xl token)
  const topOffset = 52 + index * 24;

  const isInput = type === 'target';

  return (
    <div style={{ position: 'absolute', top: `${topOffset}px`, left: isInput ? 0 : undefined, right: isInput ? undefined : 0 }}>
      <Handle
        type={type}
        position={position}
        id={port.id}
        style={{
          background: color,
          width: `${size}px`,
          height: `${size}px`,
          borderRadius,
          transform,
          border: '2px solid #0a0a14',
          top: 0,
          position: 'relative',
        }}
      />
      <span
        style={{
          position: 'absolute',
          top: '-2px',
          ...(isInput
            ? { left: '18px' }
            : { right: '18px' }),
          fontSize: '11px',
          fontWeight: 600,
          color: '#888',
          whiteSpace: 'nowrap',
          pointerEvents: 'none',
        }}
      >
        {port.label}
      </span>
    </div>
  );
}
