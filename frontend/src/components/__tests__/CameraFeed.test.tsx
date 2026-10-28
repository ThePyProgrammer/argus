import { act, cleanup, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import CameraFeed from '../CameraFeed';
import { useRobotStore } from '../../stores/robotStore';

afterEach(cleanup);
beforeEach(() => {
  vi.stubGlobal('ResizeObserver', class {
    observe() {}
    disconnect() {}
  });
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('CameraFeed without detections', () => {
  it('shows the full image and aligns boxes with letterboxing in a narrow pane', () => {
    vi.spyOn(Element.prototype, 'getBoundingClientRect').mockReturnValue({
      width: 160, height: 240, x: 0, y: 0, top: 0, left: 0, right: 160, bottom: 240,
      toJSON: () => ({}),
    });
    useRobotStore.setState({ robots: new Map() });
    const store = useRobotStore.getState();
    store.setRobotList(['robot_a']);
    store.setCameraUrl('robot_a', '/camera-frame.jpg');
    store.updateDetections('robot_a', {
      items: [{
        bbox_xyxy: [80, 60, 240, 180], class_id: 56, class_name: 'chair', score: 0.8,
        center: [1, 2, 3], half_extents: [0.5, 0.5, 0.5], quaternion: [0, 0, 0, 1],
      }],
      image_hw: [240, 320], capture_pose: [], capture_timestamp: 0,
      metrics: { detector_ms: 10, lifter_ms: 0, n_raw: 1, n_final: 1 },
    });

    const { getByText, getByAltText } = render(<CameraFeed robotId="robot_a" />);
    expect(getByAltText('robot_a rgb').style.objectFit).toBe('contain');
    const style = getByText('chair 80%').parentElement!.style;
    expect(style.left).toBe('40px');
    expect(style.top).toBe('90px');
    expect(style.width).toBe('80px');
    expect(style.height).toBe('60px');
  });

  it('mounts and accepts camera updates before detections arrive', () => {
    useRobotStore.setState({ robots: new Map() });
    useRobotStore.getState().setRobotList(['robot_a']);

    const { container } = render(<CameraFeed robotId="robot_a" />);
    act(() => {
      useRobotStore.getState().setCameraUrl('robot_a', '/camera-frame.jpg');
    });

    expect(container.querySelector('img')?.getAttribute('src')).toBe('/camera-frame.jpg');
  });
});
