import { describe, expect, it } from 'vitest';
import { cameraOverlayRect } from '../cameraOverlay';

describe('camera overlay image coordinates', () => {
  it('scales 320x240 detections to a larger image without assuming 640x480 input', () => {
    expect(cameraOverlayRect([80, 60, 240, 180], 320, 240, 640, 480)).toEqual({
      left: 160, top: 120, width: 320, height: 240,
    });
  });

  it('accounts for horizontal cropping in the narrow RGB pane', () => {
    expect(cameraOverlayRect([80, 60, 240, 180], 320, 240, 160, 240)).toEqual({
      left: 0, top: 60, width: 160, height: 120,
    });
  });

  it('accounts for vertical cropping in a wide pane', () => {
    expect(cameraOverlayRect([80, 60, 240, 180], 320, 240, 640, 240)).toEqual({
      left: 160, top: 0, width: 320, height: 240,
    });
  });
});
