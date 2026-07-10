import { render, screen } from '@testing-library/react';
import { describe, it, expect, beforeEach } from 'vitest';
import CameraFeed from './CameraFeed';
import { useRobotStore } from '../stores/robotStore';

function resetRobotStore(): void {
  useRobotStore.setState({
    robots: new Map(),
    pointCloudPositions: [],
    pointCloudColors: [],
    colorMode: 'robot_tint',
    totalCoverage: 0,
    mergeCount: 0,
    elapsed: 0,
  });
}

describe('CameraFeed', () => {
  beforeEach(() => resetRobotStore());

  it('renders a robot feed when detections have not arrived yet', () => {
    useRobotStore.getState().setRobotList(['robot_a']);

    render(<CameraFeed robotId="robot_a" />);

    expect(screen.getByText('robot_a')).toBeTruthy();
    expect(screen.getByText('No RGB')).toBeTruthy();
    expect(screen.getByText('No depth')).toBeTruthy();
  });
});
