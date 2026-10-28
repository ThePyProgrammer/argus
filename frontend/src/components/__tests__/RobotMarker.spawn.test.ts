import * as THREE from 'three';
import { expect, it, vi } from 'vitest';
import { RobotMarkerManager } from '../RobotMarker';
const loader = vi.hoisted(() => ({ loaded: null as null | ((gltf: { scene: THREE.Group }) => void) }));
vi.mock('three/addons/loaders/GLTFLoader.js', () => ({ GLTFLoader: class {
  load(_url: string, onLoad: typeof loader.loaded) { loader.loaded = onLoad; }
} }));
it('keeps spawn position and heading when the dog asset finishes loading', () => {
  const scene = new THREE.Group();
  const manager = new RobotMarkerManager(scene);
  manager.updateRobot('robot_b', [4, -2, .3], 1, [], 'initializing', Math.PI);
  loader.loaded!({ scene: new THREE.Group() });
  const dog = scene.getObjectByName('robot-marker-robot_b')!;
  expect(dog.position.toArray()).toEqual([4, -2, .3]);
  expect(dog.rotation.z).toBeCloseTo(Math.PI);
  manager.dispose();
});
