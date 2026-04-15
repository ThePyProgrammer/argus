/**
 * Plan 07-06 target — DET-PIPELINE-02 port colors + shapes extension.
 *
 * Asserts PORT_COLORS, PORT_SHAPES, CATEGORY_COLORS extended with the
 * exact hex values locked by UI-SPEC §Port Data Type Colors table.
 */
import { describe, it, expect } from 'vitest';

describe.skip('PORT_COLORS extension (Plan 07-06)', () => {
  it('maps Detections2D to coral #ff8a65', () => {
    // TODO Plan 07-06: import PORT_COLORS; assert PORT_COLORS.Detections2D === '#ff8a65'.
    expect(false).toBe(true);
  });

  it('maps Detections3D to pink #ec407a', () => {
    // TODO Plan 07-06: PORT_COLORS.Detections3D === '#ec407a'.
    expect(false).toBe(true);
  });

  it('maps Tracks to teal #26a69a', () => {
    // TODO Plan 07-06: PORT_COLORS.Tracks === '#26a69a'.
    expect(false).toBe(true);
  });

  it('maps all three new port types to circle shape', () => {
    // TODO Plan 07-06: PORT_SHAPES.Detections2D / Detections3D / Tracks === 'circle'.
    expect(false).toBe(true);
  });

  it('maps perception category to magenta #ad1457', () => {
    // TODO Plan 07-06: CATEGORY_COLORS.perception === '#ad1457'.
    expect(false).toBe(true);
  });
});
