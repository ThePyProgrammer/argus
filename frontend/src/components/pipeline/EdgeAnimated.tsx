import { BaseEdge, getBezierPath } from '@xyflow/react';
import type { EdgeProps } from '@xyflow/react';
import type { PipelineEdgeData } from '../../utils/pipelineTypes';

// Check for reduced motion preference once at module load
const prefersReducedMotion =
  typeof window !== 'undefined'
    ? window.matchMedia('(prefers-reduced-motion: reduce)').matches
    : false;

/**
 * Custom edge with flowing dot animation when pipeline is running (fps > 0).
 * Shows throughput label at edge midpoint.
 * Respects prefers-reduced-motion.
 */
function EdgeAnimated({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
}: EdgeProps) {
  const edgeData = data as unknown as PipelineEdgeData | undefined;
  const [edgePath] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  const isActive = (edgeData?.fps ?? 0) > 0;
  const midX = (sourceX + targetX) / 2;
  const midY = (sourceY + targetY) / 2;

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        style={{
          stroke: isActive ? '#4fc3f7' : '#4a4a6a',
          strokeWidth: 2,
        }}
      />
      {isActive && !prefersReducedMotion && (
        <circle r="3" fill="#4fc3f7" opacity={0.6}>
          <animateMotion dur="2s" repeatCount="indefinite" path={edgePath} />
        </circle>
      )}
      {isActive && (
        <text
          x={midX}
          y={midY - 8}
          style={{
            fontSize: '10px',
            fill: '#888',
            textAnchor: 'middle',
            pointerEvents: 'none',
          }}
        >
          {edgeData!.fps} fps
        </text>
      )}
    </>
  );
}

// CRITICAL: edgeTypes at MODULE scope (same pattern as nodeTypes) -- Pitfall 1
export const edgeTypes = { animated: EdgeAnimated };

export { EdgeAnimated };
