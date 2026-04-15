/**
 * Plan 07-06 target — DET-PIPELINE-02 port colors + shapes extension.
 * Depends on Plan 07-07 running first (same wave) to populate PORT_COLORS,
 * PORT_SHAPES, CATEGORY_COLORS maps. TypeScript's strict Record<> typing
 * enforces this ordering at compile time.
 */
import { describe, it, expect } from 'vitest';
import { PORT_COLORS, PORT_SHAPES, CATEGORY_COLORS } from '../nodeDefinitions';

describe('PORT_COLORS extension (Plan 07-06 + 07-07)', () => {
  it('maps Detections2D to coral #ff8a65', () => {
    expect(PORT_COLORS.Detections2D).toBe('#ff8a65');
  });

  it('maps Detections3D to pink #ec407a', () => {
    expect(PORT_COLORS.Detections3D).toBe('#ec407a');
  });

  it('maps Tracks to teal #26a69a', () => {
    expect(PORT_COLORS.Tracks).toBe('#26a69a');
  });

  it('maps all three new port types to circle shape', () => {
    expect(PORT_SHAPES.Detections2D).toBe('circle');
    expect(PORT_SHAPES.Detections3D).toBe('circle');
    expect(PORT_SHAPES.Tracks).toBe('circle');
  });

  it('maps perception category to magenta #ad1457', () => {
    expect(CATEGORY_COLORS.perception).toBe('#ad1457');
  });
});
