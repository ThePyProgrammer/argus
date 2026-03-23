import * as THREE from 'three';

/**
 * Imperative Three.js point cloud manager.
 *
 * Pre-allocates a 200k-point buffer (positions: 2.4 MB, colors: 600 KB)
 * and uses setDrawRange to render only the active subset. Supports both
 * full replacement and incremental delta appends.
 */
export class PointCloudManager {
  private geometry: THREE.BufferGeometry;
  private points: THREE.Points;
  private maxPoints = 200_000;
  private currentCount = 0;

  constructor(scene: THREE.Object3D) {
    this.geometry = new THREE.BufferGeometry();

    const positions = new Float32Array(this.maxPoints * 3);
    const colors = new Uint8Array(this.maxPoints * 3);

    this.geometry.setAttribute(
      'position',
      new THREE.BufferAttribute(positions, 3),
    );
    // normalized: true converts Uint8 [0,255] -> float [0,1] for the shader
    this.geometry.setAttribute(
      'color',
      new THREE.BufferAttribute(colors, 3, true),
    );
    this.geometry.setDrawRange(0, 0);

    const material = new THREE.PointsMaterial({
      size: 0.05,
      vertexColors: true,
      sizeAttenuation: true,
    });

    this.points = new THREE.Points(this.geometry, material);
    scene.add(this.points);
  }

  /**
   * Replace entire cloud with new data. Resets currentCount.
   * @param positions Array of [x, y, z] tuples
   * @param colors Optional array of [r, g, b] tuples (0-255). Defaults to white.
   */
  updateFull(positions: number[][], colors?: number[][]): void {
    const count = Math.min(positions.length, this.maxPoints);
    const posAttr = this.geometry.attributes.position as THREE.BufferAttribute;
    const colAttr = this.geometry.attributes.color as THREE.BufferAttribute;
    const posArr = posAttr.array as Float32Array;
    const colArr = colAttr.array as Uint8Array;

    for (let i = 0; i < count; i++) {
      const i3 = i * 3;
      const p = positions[i];
      posArr[i3] = p[0];
      posArr[i3 + 1] = p[1];
      posArr[i3 + 2] = p[2];

      if (colors && colors[i]) {
        const c = colors[i];
        colArr[i3] = c[0];
        colArr[i3 + 1] = c[1];
        colArr[i3 + 2] = c[2];
      } else {
        colArr[i3] = 255;
        colArr[i3 + 1] = 255;
        colArr[i3 + 2] = 255;
      }
    }

    this.currentCount = count;
    posAttr.needsUpdate = true;
    colAttr.needsUpdate = true;
    this.geometry.setDrawRange(0, this.currentCount);
    this.geometry.computeBoundingSphere();
  }

  /**
   * Append new points to the existing buffer at currentCount offset.
   * @param newPositions Array of [x, y, z] tuples
   * @param newColors Optional array of [r, g, b] tuples (0-255). Defaults to white.
   */
  appendDelta(newPositions: number[][], newColors?: number[][]): void {
    const available = this.maxPoints - this.currentCount;
    const count = Math.min(newPositions.length, available);
    if (count <= 0) return;

    const posAttr = this.geometry.attributes.position as THREE.BufferAttribute;
    const colAttr = this.geometry.attributes.color as THREE.BufferAttribute;
    const posArr = posAttr.array as Float32Array;
    const colArr = colAttr.array as Uint8Array;

    const offset = this.currentCount * 3;
    for (let i = 0; i < count; i++) {
      const i3 = offset + i * 3;
      const p = newPositions[i];
      posArr[i3] = p[0];
      posArr[i3 + 1] = p[1];
      posArr[i3 + 2] = p[2];

      if (newColors && newColors[i]) {
        const c = newColors[i];
        colArr[i3] = c[0];
        colArr[i3 + 1] = c[1];
        colArr[i3 + 2] = c[2];
      } else {
        colArr[i3] = 255;
        colArr[i3 + 1] = 255;
        colArr[i3 + 2] = 255;
      }
    }

    this.currentCount += count;
    posAttr.needsUpdate = true;
    colAttr.needsUpdate = true;
    this.geometry.setDrawRange(0, this.currentCount);
    this.geometry.computeBoundingSphere();
  }

  /** Shift the entire cloud by an offset (in worldRoot Z-up coords). */
  setOffset(x: number, y: number, z: number): void {
    this.points.position.set(x, y, z);
  }

  /** Control visibility for cross-fade transitions. */
  setVisible(visible: boolean): void {
    this.points.visible = visible;
  }

  /** Access material for opacity control during cross-fade. */
  getMaterial(): THREE.PointsMaterial {
    return this.points.material as THREE.PointsMaterial;
  }

  /** Release GPU resources. */
  dispose(): void {
    this.geometry.dispose();
    (this.points.material as THREE.Material).dispose();
  }
}
