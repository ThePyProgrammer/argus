import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import RobotCard from '../RobotCard';
import type { RobotInfo } from '../../stores/robotStore';

function robot(overrides: Partial<RobotInfo> = {}): RobotInfo {
  return {
    id: 'robot_a',
    colorIndex: 0,
    position: [0, 0, 0],
    rotation: [1, 0, 0, 0, 1, 0, 0, 0, 1],
    coveragePct: 10,
    voxelCount: 20,
    action: 'idle',
    cameraUrl: null,
    depthUrl: null,
    trajectory: [],
    trajectoryAlphas: [],
    detections_3d: null,
    sceneDescription: null,
    sceneObjects: [],
    trackingStatus: 'ok',
    bodyYaw: 0,
    platform: 'agibot_x2',
    platformMetadata: { name: 'agibot_x2', display_name: 'AGIBOT X2 Ultra' },
    runtimeState: 'fallen',
    fallReason: 'base_height',
    disabled: true,
    controllerHealth: { policy_loaded: false, message: 'ok' },
    collisionCount: 1,
    nearMissCount: 2,
    ...overrides,
  };
}

describe('RobotCard platform runtime state', () => {
  it('shows platform, runtime, fall, controller, and collision state', () => {
    render(<RobotCard robot={robot()} />);

    expect(screen.getByText('AGIBOT X2 Ultra')).toBeTruthy();
    expect(screen.getByText('fallen')).toBeTruthy();
    expect(screen.getByText('Fall: base_height')).toBeTruthy();
    expect(screen.getByText('Controller: no policy')).toBeTruthy();
    expect(screen.getByText('Collisions: 1')).toBeTruthy();
    expect(screen.getByText('Near misses: 2')).toBeTruthy();
  });

  it('surfaces degraded controller health instead of ok', () => {
    render(<RobotCard robot={robot({
      controllerHealth: {
        policy_loaded: true,
        nan_guard_ok: false,
        message: 'invalid output',
      },
    })} />);

    expect(screen.queryByText('Controller: ok')).toBeNull();
    expect(screen.getByText('Controller: invalid output')).toBeTruthy();
  });

  it('trims controller health messages before treating ok as degraded', () => {
    render(<RobotCard robot={robot({
      controllerHealth: {
        policy_loaded: true,
        nan_guard_ok: false,
        message: ' ok ',
      },
    })} />);

    expect(screen.queryByText('Controller: ok')).toBeNull();
    expect(screen.getByText('Controller: degraded')).toBeTruthy();
  });
});
