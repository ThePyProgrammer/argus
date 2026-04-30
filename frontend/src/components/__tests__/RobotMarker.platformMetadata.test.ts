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

const agibotMetadata = {
  name: 'agibot_x2',
  display_name: 'AGIBOT X2 Ultra',
  footprint_radius: 0.33,
  dimensions: [0.46, 0.21, 1.31] as [number, number, number],
  marker_asset: null,
};

function getMarkerMesh(scene: THREE.Object3D, robotId: string): THREE.Mesh {
  const marker = scene.getObjectByName(`robot-marker-${robotId}`);
  expect(marker).toBeTruthy();
  expect((marker as THREE.Mesh).isMesh).toBe(true);
  return marker as THREE.Mesh;
}

function getGeometrySize(mesh: THREE.Mesh): THREE.Vector3 {
  mesh.geometry.computeBoundingBox();
  const box = mesh.geometry.boundingBox;
  expect(box).toBeTruthy();
  return box!.getSize(new THREE.Vector3());
}

describe('RobotMarkerManager platform metadata', () => {
  it('creates AGIBOT fallback marker as a capsule with local Z height from platform dimensions', () => {
    const scene = new THREE.Group();
    const manager = new RobotMarkerManager(scene);

    manager.updateRobot('robot_a', [1, 2, 0.85], 0, undefined, 'ok', 0, agibotMetadata);

    const marker = getMarkerMesh(scene, 'robot_a');
    expect(marker.position.x).toBe(1);
    expect(marker.position.y).toBe(2);
    expect(marker.position.z).toBe(0.85);
    expect(marker.geometry).toBeInstanceOf(THREE.CapsuleGeometry);

    const size = getGeometrySize(marker);
    expect(size.z).toBeCloseTo(agibotMetadata.dimensions[2], 1);
    expect(size.z).toBeGreaterThan(size.x);
    expect(size.z).toBeGreaterThan(size.y);

    manager.dispose();
  });

  it('keeps null platform metadata on the default sphere fallback', () => {
    const scene = new THREE.Group();
    const manager = new RobotMarkerManager(scene);

    manager.updateRobot('robot_default', [0, 0, 0.15], 1, undefined, 'ok', 0, null);

    const marker = getMarkerMesh(scene, 'robot_default');
    expect(marker.geometry).toBeInstanceOf(THREE.SphereGeometry);

    const size = getGeometrySize(marker);
    expect(size.x).toBeCloseTo(size.y, 5);
    expect(size.y).toBeCloseTo(size.z, 5);

    manager.dispose();
  });

  it('replaces a default fallback marker when AGIBOT metadata arrives later', () => {
    const scene = new THREE.Group();
    const manager = new RobotMarkerManager(scene);

    manager.updateRobot('robot_late', [0, 0, 0.15], 2, undefined, 'ok', 0, null);
    const initialMarker = getMarkerMesh(scene, 'robot_late');
    expect(initialMarker.geometry).toBeInstanceOf(THREE.SphereGeometry);

    manager.updateRobot('robot_late', [3, 4, 1.31], 2, undefined, 'lost', Math.PI / 4, agibotMetadata);

    const updatedMarker = getMarkerMesh(scene, 'robot_late');
    expect(updatedMarker).not.toBe(initialMarker);
    expect(updatedMarker.geometry).toBeInstanceOf(THREE.CapsuleGeometry);
    expect(updatedMarker.position.x).toBe(3);
    expect(updatedMarker.position.y).toBe(4);
    expect(updatedMarker.position.z).toBe(1.31);
    expect(updatedMarker.rotation.z).toBeCloseTo(Math.PI / 4);

    const size = getGeometrySize(updatedMarker);
    expect(size.z).toBeCloseTo(agibotMetadata.dimensions[2], 1);
    expect(size.z).toBeGreaterThan(size.x);
    expect(size.z).toBeGreaterThan(size.y);

    manager.dispose();
  });
});
