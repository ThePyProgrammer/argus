import { beforeEach, describe, expect, it } from 'vitest';
import { useRobotStore } from '../robotStore';

function resetStore(): void {
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

describe('robotStore platform state', () => {
  beforeEach(() => resetStore());

  it('stores platform metadata from robot list', () => {
    useRobotStore.getState().setRobotList(['robot_a'], {
      robot_a: {
        name: 'agibot_x2',
        display_name: 'AGIBOT X2 Ultra',
        footprint_radius: 0.33,
        dimensions: [0.46, 0.21, 1.31],
        marker_asset: null,
      },
    });

    const robot = useRobotStore.getState().robots.get('robot_a')!;
    expect(robot.platform).toBe('agibot_x2');
    expect(robot.platformMetadata?.display_name).toBe('AGIBOT X2 Ultra');
    expect(robot.platformMetadata?.footprint_radius).toBe(0.33);
  });

  it('updates runtime status from stats payload', () => {
    useRobotStore.getState().setRobotList(['robot_a']);

    useRobotStore.getState().updateStats({
      total_coverage: 10,
      merge_count: 1,
      elapsed: 2,
      robots: {
        robot_a: {
          coverage_pct: 10,
          voxel_count: 20,
          action: 'fallen',
          platform: { name: 'agibot_x2', display_name: 'AGIBOT X2 Ultra' },
          runtime_status: {
            state: 'fallen',
            fall_reason: 'base_height',
            disabled: true,
            controller_health: { policy_loaded: false, message: 'ok' },
            collision_count: 1,
            near_miss_count: 2,
          },
        },
      },
    });

    const robot = useRobotStore.getState().robots.get('robot_a')!;
    expect(robot.runtimeState).toBe('fallen');
    expect(robot.fallReason).toBe('base_height');
    expect(robot.disabled).toBe(true);
    expect(robot.controllerHealth?.policy_loaded).toBe(false);
    expect(robot.collisionCount).toBe(1);
    expect(robot.nearMissCount).toBe(2);
  });
});
