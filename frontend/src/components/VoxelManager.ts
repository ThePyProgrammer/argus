import * as THREE from 'three';

/**
 * Imperative Three.js voxel grid rendering manager.
 *
 * Renders voxel cubes using InstancedMesh for single-draw-call performance.
 * Same imperative pattern as PointCloudManager: constructor takes scene,
 * imperative update methods, dispose() cleanup.
 */
export class VoxelManager {
  private mesh: THREE.InstancedMesh;
  private dummy = new THREE.Object3D();
  private maxVoxels = 200_000;

  constructor(scene: THREE.Object3D, voxelSize: number = 0.1) {
    const geometry = new THREE.BoxGeometry(voxelSize, voxelSize, voxelSize);
    const material = new THREE.MeshLambertMaterial({
      vertexColors: false,
      transparent: true,
      opacity: 1.0,
    });
    this.mesh = new THREE.InstancedMesh(geometry, material, this.maxVoxels);
    this.mesh.count = 0;
    this.mesh.visible = false; // Hidden by default (cloud mode is default)
    scene.add(this.mesh);
  }

  /**
   * Replace all voxel instances with new positions/colors.
   * @param positions Array of [x, y, z] tuples for voxel center positions
   * @param colors Optional array of [r, g, b] tuples (0-255)
   */
  updateFull(positions: number[][], colors?: number[][]): void {
    const count = Math.min(positions.length, this.maxVoxels);
    for (let i = 0; i < count; i++) {
      this.dummy.position.set(
        positions[i][0],
        positions[i][1],
        positions[i][2],
      );
      this.dummy.updateMatrix();
      this.mesh.setMatrixAt(i, this.dummy.matrix);
      if (colors?.[i]) {
        this.mesh.setColorAt(
          i,
          new THREE.Color(
            colors[i][0] / 255,
            colors[i][1] / 255,
            colors[i][2] / 255,
          ),
        );
      }
    }
    this.mesh.count = count;
    this.mesh.instanceMatrix.needsUpdate = true;
    if (this.mesh.instanceColor) this.mesh.instanceColor.needsUpdate = true;
  }

  /** Control visibility for cross-fade transitions. */
  setVisible(visible: boolean): void {
    this.mesh.visible = visible;
  }

  /** Access material for opacity control during cross-fade. */
  getMaterial(): THREE.MeshLambertMaterial {
    return this.mesh.material as THREE.MeshLambertMaterial;
  }

  /** Release GPU resources. */
  dispose(): void {
    this.mesh.geometry.dispose();
    (this.mesh.material as THREE.Material).dispose();
    this.mesh.parent?.remove(this.mesh);
  }
}
