import * as THREE from 'three';
import { describe, expect, it, vi } from 'vitest';
import { RobotMarkerManager } from '../RobotMarker';

vi.mock('three/addons/loaders/GLTFLoader.js', () => ({
  GLTFLoader: class {
    load(_url: string, _onLoad: unknown, _onProgress: unknown, onError: () => void) {
      onError();
    }
  },
}));

describe('RobotMarkerManager platform metadata', () => {
  it('creates humanoid fallback marker scaled from platform dimensions', () => {
    const scene = new THREE.Group();
    const manager = new RobotMarkerManager(scene);

    manager.updateRobot(
      'robot_a',
      [1, 2, 0.85],
      0,
      undefined,
      'ok',
      0,
      {
        name: 'agibot_x2',
        display_name: 'AGIBOT X2 Ultra',
        footprint_radius: 0.33,
        dimensions: [0.46, 0.21, 1.31],
        marker_asset: null,
      },
    );

    const marker = scene.getObjectByName('robot-marker-robot_a')!;
    expect(marker).toBeTruthy();
    expect(marker.position.x).toBe(1);
    expect(marker.position.y).toBe(2);
    expect(marker.position.z).toBe(0.85);
    expect(marker.scale.z).toBeGreaterThan(1);

    manager.dispose();
  });
});
