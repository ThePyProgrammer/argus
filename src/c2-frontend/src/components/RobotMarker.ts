import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OKABE_ITO } from '../utils/palette';

/**
 * Manages per-robot Go2 mesh markers in the Three.js scene.
 *
 * Loads the Go2 GLB model once, clones it per robot, and tints each
 * clone with the robot's palette color. Falls back to a colored sphere
 * if the GLB fails to load.
 */
export class RobotMarkerManager {
  private markers: Map<string, THREE.Object3D> = new Map();
  private scene: THREE.Object3D;
  private templateModel: THREE.Group | null = null;
  private modelLoaded = false;
  private modelFailed = false;
  private pendingUpdates: Map<string, { position: [number, number, number]; colorIndex: number }> = new Map();
  private fallbackGeometry: THREE.SphereGeometry;

  constructor(scene: THREE.Object3D) {
    this.scene = scene;
    this.fallbackGeometry = new THREE.SphereGeometry(0.15, 16, 16);
    this.loadModel();
  }

  private loadModel(): void {
    const loader = new GLTFLoader();
    loader.load(
      '/public/go2.glb',
      (gltf) => {
        this.templateModel = gltf.scene;
        // Scale down — Go2 OBJ meshes are in meters but may be oversized
        this.templateModel.scale.setScalar(1.0);
        this.modelLoaded = true;

        // Process any robots that were added before model loaded
        for (const [robotId, update] of this.pendingUpdates) {
          this.createMeshMarker(robotId, update.position, update.colorIndex);
        }
        this.pendingUpdates.clear();
      },
      undefined,
      () => {
        console.warn('[RobotMarker] Go2 GLB not available, using sphere fallback');
        this.modelFailed = true;

        // Create sphere fallbacks for pending robots
        for (const [robotId, update] of this.pendingUpdates) {
          this.createSphereMarker(robotId, update.position, update.colorIndex);
        }
        this.pendingUpdates.clear();
      },
    );
  }

  private createMeshMarker(
    robotId: string,
    position: [number, number, number],
    colorIndex: number,
  ): void {
    if (!this.templateModel) return;

    const clone = this.templateModel.clone();
    const color = new THREE.Color(OKABE_ITO[colorIndex % 8]);

    // Tint all child meshes with the robot's color
    clone.traverse((child) => {
      if ((child as THREE.Mesh).isMesh) {
        const mesh = child as THREE.Mesh;
        mesh.material = new THREE.MeshStandardMaterial({
          color,
          emissive: color,
          emissiveIntensity: 0.2,
          transparent: true,
          opacity: 0.85,
        });
      }
    });

    clone.name = `robot-marker-${robotId}`;
    clone.position.set(position[0], position[1], position[2]);
    this.scene.add(clone);
    this.markers.set(robotId, clone);
  }

  private createSphereMarker(
    robotId: string,
    position: [number, number, number],
    colorIndex: number,
  ): void {
    const color = new THREE.Color(OKABE_ITO[colorIndex % 8]);
    const material = new THREE.MeshStandardMaterial({
      color,
      emissive: color,
      emissiveIntensity: 0.3,
    });
    const mesh = new THREE.Mesh(this.fallbackGeometry, material);
    mesh.name = `robot-marker-${robotId}`;
    mesh.position.set(position[0], position[1], position[2]);
    this.scene.add(mesh);
    this.markers.set(robotId, mesh);
  }

  /**
   * Apply a flat 9-element 3x3 rotation matrix (row-major, Z-up MuJoCo frame)
   * to a Three.js object that lives inside the worldRoot (which has -90° X
   * rotation for Z-up → Y-up conversion).
   *
   * Since the parent worldRoot already rotates the coordinate system, the
   * marker's local rotation must compensate: we pre-multiply by +90° X
   * (inverse of the parent's -90° X) so the final world rotation is correct.
   */
  private applyRotation(obj: THREE.Object3D, rotation: number[]): void {
    if (rotation.length !== 9) return;

    // MuJoCo Z-up rotation matrix
    const mujoco = new THREE.Matrix4();
    mujoco.set(
      rotation[0], rotation[1], rotation[2], 0,
      rotation[3], rotation[4], rotation[5], 0,
      rotation[6], rotation[7], rotation[8], 0,
      0, 0, 0, 1,
    );

    // Undo parent's -90° X rotation: pre-multiply by +90° X
    // Rx(+90°) swaps Y↔Z: [x, y, z] → [x, z, -y]
    // As a matrix: [[1,0,0],[0,0,-1],[0,1,0]]
    const undoParent = new THREE.Matrix4();
    undoParent.set(
      1, 0, 0, 0,
      0, 0, 1, 0,
      0, -1, 0, 0,
      0, 0, 0, 1,
    );

    // Local rotation = undoParent * mujocoRotation
    const local = undoParent.multiply(mujoco);
    obj.quaternion.setFromRotationMatrix(local);
  }

  /**
   * Create or update a robot marker at the given position and rotation.
   * @param robotId Unique robot identifier
   * @param position [x, y, z] world position
   * @param colorIndex Index into the Okabe-Ito palette
   * @param rotation Optional 9-element flat 3x3 rotation matrix (row-major)
   */
  updateRobot(
    robotId: string,
    position: [number, number, number],
    colorIndex: number,
    rotation?: number[],
  ): void {
    const existing = this.markers.get(robotId);

    if (existing) {
      existing.position.set(position[0], position[1], position[2]);
      if (rotation) this.applyRotation(existing, rotation);
      return;
    }

    // Model still loading — queue the update
    if (!this.modelLoaded && !this.modelFailed) {
      this.pendingUpdates.set(robotId, { position, colorIndex });
      return;
    }

    // Create new marker
    if (this.modelLoaded && this.templateModel) {
      this.createMeshMarker(robotId, position, colorIndex);
    } else {
      this.createSphereMarker(robotId, position, colorIndex);
    }
  }

  /**
   * Get the position of a robot marker (for camera targeting).
   * @returns The [x, y, z] position or null if robot not found.
   */
  centerOnRobot(robotId: string): [number, number, number] | null {
    const obj = this.markers.get(robotId);
    if (!obj) return null;
    return [obj.position.x, obj.position.y, obj.position.z];
  }

  /** Release GPU resources for all markers. */
  dispose(): void {
    for (const obj of this.markers.values()) {
      obj.traverse((child) => {
        if ((child as THREE.Mesh).isMesh) {
          const mesh = child as THREE.Mesh;
          if (mesh.material) (mesh.material as THREE.Material).dispose();
          if (mesh.geometry) mesh.geometry.dispose();
        }
      });
      this.scene.remove(obj);
    }
    this.markers.clear();
    this.fallbackGeometry.dispose();
  }
}
