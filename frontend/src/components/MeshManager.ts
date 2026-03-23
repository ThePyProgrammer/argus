import * as THREE from 'three';

/**
 * Imperative Three.js mesh rendering manager.
 *
 * Renders triangulated surfaces via indexed BufferGeometry with vertex normals.
 * Same imperative pattern as PointCloudManager: constructor takes scene,
 * imperative update methods, dispose() cleanup.
 */
export class MeshManager {
  private meshObj: THREE.Mesh;
  private geometry: THREE.BufferGeometry;

  constructor(scene: THREE.Object3D) {
    this.geometry = new THREE.BufferGeometry();
    const material = new THREE.MeshPhongMaterial({
      vertexColors: true,
      transparent: true,
      opacity: 1.0,
      side: THREE.DoubleSide,
      flatShading: true,
    });
    this.meshObj = new THREE.Mesh(this.geometry, material);
    this.meshObj.visible = false; // Hidden by default
    scene.add(this.meshObj);
  }

  /**
   * Replace mesh geometry with new vertex/face data from server-side reconstruction.
   * @param vertices Array of [x, y, z] tuples for vertex positions
   * @param faces Array of [i, j, k] tuples for triangle face indices
   * @param colors Optional array of [r, g, b] tuples (0-1 range) per vertex
   */
  updateMesh(
    vertices: number[][],
    faces: number[][],
    colors?: number[][] | null,
  ): void {
    // Build flat Float32Array for positions
    const positions = new Float32Array(vertices.length * 3);
    for (let i = 0; i < vertices.length; i++) {
      positions[i * 3] = vertices[i][0];
      positions[i * 3 + 1] = vertices[i][1];
      positions[i * 3 + 2] = vertices[i][2];
    }
    this.geometry.setAttribute(
      'position',
      new THREE.BufferAttribute(positions, 3),
    );

    // Build index buffer from faces
    const indices = new Uint32Array(faces.length * 3);
    for (let i = 0; i < faces.length; i++) {
      indices[i * 3] = faces[i][0];
      indices[i * 3 + 1] = faces[i][1];
      indices[i * 3 + 2] = faces[i][2];
    }
    this.geometry.setIndex(new THREE.BufferAttribute(indices, 1));

    // Vertex colors if provided
    if (colors && colors.length === vertices.length) {
      const colorArr = new Float32Array(colors.length * 3);
      for (let i = 0; i < colors.length; i++) {
        colorArr[i * 3] = colors[i][0];
        colorArr[i * 3 + 1] = colors[i][1];
        colorArr[i * 3 + 2] = colors[i][2];
      }
      this.geometry.setAttribute(
        'color',
        new THREE.BufferAttribute(colorArr, 3),
      );
    }

    this.geometry.computeVertexNormals();
    this.geometry.computeBoundingSphere();
  }

  /** Control visibility for cross-fade transitions. */
  setVisible(visible: boolean): void {
    this.meshObj.visible = visible;
  }

  /** Access material for opacity control during cross-fade. */
  getMaterial(): THREE.MeshPhongMaterial {
    return this.meshObj.material as THREE.MeshPhongMaterial;
  }

  /** Release GPU resources. */
  dispose(): void {
    this.geometry.dispose();
    (this.meshObj.material as THREE.Material).dispose();
    this.meshObj.parent?.remove(this.meshObj);
  }
}
