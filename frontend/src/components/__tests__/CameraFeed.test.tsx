import { act, cleanup, render } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import CameraFeed from '../CameraFeed';
import { useRobotStore } from '../../stores/robotStore';

afterEach(cleanup);

describe('CameraFeed without detections', () => {
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
