import * as THREE from 'three';
import { OKABE_ITO_RGB } from '../utils/palette';

/**
 * Manages fading trajectory trail line segments per robot.
 *
 * Each trail is rendered as LineSegments with vertex colors that fade
 * from dark (old positions) to bright (recent positions) using the
 * alpha values to modulate base RGB color brightness. This avoids the
 * LineBasicMaterial per-vertex alpha limitation.
 */
export class TrajectoryTrailManager {
  private trails: Map<string, THREE.LineSegments> = new Map();
  private scene: THREE.Object3D;

  constructor(scene: THREE.Object3D) {
    this.scene = scene;
  }

  /**
   * Update or create the trajectory trail for a robot.
   * @param robotId Unique robot identifier
   * @param positions Array of [x, y, z] waypoints (ordered old -> recent)
   * @param alphas Array of alpha values (0-255) per waypoint
   * @param colorIndex Index into the Okabe-Ito palette
   */
  updateTrail(
    robotId: string,
    positions: number[][],
    alphas: number[],
    colorIndex: number,
  ): void {
    // Need at least 2 points to form a segment
    if (positions.length < 2) return;

    // Remove old trail
    const existing = this.trails.get(robotId);
    if (existing) {
      existing.geometry.dispose();
      (existing.material as THREE.Material).dispose();
      this.scene.remove(existing);
    }

    const segmentCount = positions.length - 1;
    // Each segment has 2 vertices
    const vertexCount = segmentCount * 2;

    const posArray = new Float32Array(vertexCount * 3);
    const colArray = new Float32Array(vertexCount * 3);

    const baseRGB = OKABE_ITO_RGB[colorIndex % 8];
    const baseR = baseRGB[0] / 255;
    const baseG = baseRGB[1] / 255;
    const baseB = baseRGB[2] / 255;

    for (let i = 0; i < segmentCount; i++) {
      const v0 = i * 2;
      const v1 = v0 + 1;

      // Positions: segment from positions[i] to positions[i+1]
      const p0 = positions[i];
      const p1 = positions[i + 1];
      posArray[v0 * 3] = p0[0];
      posArray[v0 * 3 + 1] = p0[1];
      posArray[v0 * 3 + 2] = p0[2];
      posArray[v1 * 3] = p1[0];
      posArray[v1 * 3 + 1] = p1[1];
      posArray[v1 * 3 + 2] = p1[2];

      // Colors: fade by multiplying base color with alpha/255
      const a0 = (alphas[i] ?? 255) / 255;
      const a1 = (alphas[i + 1] ?? 255) / 255;

      colArray[v0 * 3] = baseR * a0;
      colArray[v0 * 3 + 1] = baseG * a0;
      colArray[v0 * 3 + 2] = baseB * a0;
      colArray[v1 * 3] = baseR * a1;
      colArray[v1 * 3 + 1] = baseG * a1;
      colArray[v1 * 3 + 2] = baseB * a1;
    }

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute(
      'position',
      new THREE.Float32BufferAttribute(posArray, 3),
    );
    geometry.setAttribute(
      'color',
      new THREE.Float32BufferAttribute(colArray, 3),
    );

    const material = new THREE.LineBasicMaterial({
      vertexColors: true,
      linewidth: 1,
    });

    const lineSegments = new THREE.LineSegments(geometry, material);
    lineSegments.name = `trail-${robotId}`;
    this.scene.add(lineSegments);
    this.trails.set(robotId, lineSegments);
  }

  /** Release GPU resources for all trails. */
  dispose(): void {
    for (const trail of this.trails.values()) {
      trail.geometry.dispose();
      (trail.material as THREE.Material).dispose();
      this.scene.remove(trail);
    }
    this.trails.clear();
  }
}
