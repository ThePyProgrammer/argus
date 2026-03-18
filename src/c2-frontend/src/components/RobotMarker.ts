import * as THREE from 'three';
import { OKABE_ITO } from '../utils/palette';

/**
 * Manages per-robot colored sphere markers in the Three.js scene.
 *
 * Creates or updates a sphere at each robot's reported position.
 * Sphere geometry is shared across all markers for efficiency.
 */
export class RobotMarkerManager {
  private markers: Map<string, THREE.Mesh> = new Map();
  private scene: THREE.Object3D;
  private sharedGeometry: THREE.SphereGeometry;

  constructor(scene: THREE.Object3D) {
    this.scene = scene;
    // Shared geometry: radius 0.15, 16x16 segments
    this.sharedGeometry = new THREE.SphereGeometry(0.15, 16, 16);
  }

  /**
   * Create or update a robot marker at the given position.
   * @param robotId Unique robot identifier
   * @param position [x, y, z] world position
   * @param colorIndex Index into the Okabe-Ito palette
   */
  updateRobot(
    robotId: string,
    position: [number, number, number],
    colorIndex: number,
  ): void {
    let mesh = this.markers.get(robotId);

    if (!mesh) {
      const material = new THREE.MeshStandardMaterial({
        color: new THREE.Color(OKABE_ITO[colorIndex % 8]),
        emissive: new THREE.Color(OKABE_ITO[colorIndex % 8]),
        emissiveIntensity: 0.3,
      });
      mesh = new THREE.Mesh(this.sharedGeometry, material);
      mesh.name = `robot-marker-${robotId}`;
      this.scene.add(mesh);
      this.markers.set(robotId, mesh);
    }

    mesh.position.set(position[0], position[1], position[2]);
  }

  /**
   * Get the position of a robot marker (for camera targeting).
   * @returns The [x, y, z] position or null if robot not found.
   */
  centerOnRobot(robotId: string): [number, number, number] | null {
    const mesh = this.markers.get(robotId);
    if (!mesh) return null;
    return [mesh.position.x, mesh.position.y, mesh.position.z];
  }

  /** Release GPU resources for all markers. */
  dispose(): void {
    for (const mesh of this.markers.values()) {
      (mesh.material as THREE.Material).dispose();
      this.scene.remove(mesh);
    }
    this.markers.clear();
    this.sharedGeometry.dispose();
  }
}
