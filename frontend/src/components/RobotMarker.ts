import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import type { PlatformMetadata } from '../utils/messageTypes';
import { OKABE_ITO } from '../utils/palette';

/** Tracking status colors for robot markers (SLAM tracking state). */
const STATUS_COLORS: Record<string, number> = {
  ok: 0x00cc00,            // green
  lost: 0xcc0000,          // red
  relocalizing: 0xcccc00,  // yellow
  initializing: 0xcccc00,  // yellow
};

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
  private pendingUpdates: Map<string, { position: [number, number, number]; colorIndex: number; platformMetadata?: PlatformMetadata | null }> = new Map();
  private fallbackGeometry: THREE.SphereGeometry;
  private fallbackMarkerKeys: Map<string, string> = new Map();

  constructor(scene: THREE.Object3D) {
    this.scene = scene;
    this.fallbackGeometry = new THREE.SphereGeometry(0.15, 16, 16);
    this.loadModel();
  }

  private loadModel(): void {
    const loader = new GLTFLoader();
    loader.load(
      '/go2.glb',
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

        // Create fallback markers for pending robots
        for (const [robotId, update] of this.pendingUpdates) {
          this.createFallbackMarker(robotId, update.position, update.colorIndex, update.platformMetadata);
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

  private getFallbackMarkerKey(platformMetadata?: PlatformMetadata | null): string {
    if (platformMetadata?.name !== 'agibot_x2') {
      return 'sphere';
    }

    const radius = platformMetadata.footprint_radius ?? 0.15;
    const height = platformMetadata.dimensions?.[2] ?? radius * 2;
    return `agibot_x2:${radius}:${height}`;
  }

  private disposeMarkerObject(obj: THREE.Object3D): void {
    obj.traverse((child) => {
      if ((child as THREE.Mesh).isMesh) {
        const mesh = child as THREE.Mesh;
        const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
        for (const material of materials) {
          material.dispose();
        }
        if (mesh.geometry && mesh.geometry !== this.fallbackGeometry) {
          mesh.geometry.dispose();
        }
      }
    });
  }

  private removeMarker(robotId: string): void {
    const obj = this.markers.get(robotId);
    if (!obj) return;

    this.disposeMarkerObject(obj);
    this.scene.remove(obj);
    this.markers.delete(robotId);
    this.fallbackMarkerKeys.delete(robotId);
  }

  private createFallbackMarker(
    robotId: string,
    position: [number, number, number],
    colorIndex: number,
    platformMetadata?: PlatformMetadata | null,
  ): void {
    const color = new THREE.Color(OKABE_ITO[colorIndex % 8]);
    const material = new THREE.MeshStandardMaterial({
      color,
      emissive: color,
      emissiveIntensity: 0.3,
    });
    const dims = platformMetadata?.dimensions;
    const radius = platformMetadata?.footprint_radius ?? 0.15;
    const height = dims?.[2] ?? radius * 2;
    const fallbackKey = this.getFallbackMarkerKey(platformMetadata);
    const capsuleRadius = radius * 0.45;
    const geometry = fallbackKey.startsWith('agibot_x2:')
      ? new THREE.CapsuleGeometry(capsuleRadius, Math.max(0.1, height - capsuleRadius * 2), 8, 16).rotateX(Math.PI / 2)
      : this.fallbackGeometry;
    const mesh = new THREE.Mesh(geometry, material);
    mesh.name = `robot-marker-${robotId}`;
    mesh.position.set(position[0], position[1], position[2]);
    this.scene.add(mesh);
    this.markers.set(robotId, mesh);
    this.fallbackMarkerKeys.set(robotId, fallbackKey);
  }

  /**
   * Create or update a robot marker.
   *
   * @param robotId Unique robot identifier
   * @param position [x, y, z] world position
   * @param colorIndex Index into the Okabe-Ito palette
   * @param rotation Optional 9-element flat 3x3 cam_xmat (row-major)
   * @param trackingStatus SLAM tracking state
   * @param bodyYaw MuJoCo body heading in radians (Z-axis rotation)
   * @param platformMetadata Optional robot platform metadata for fallback rendering
   */
  updateRobot(
    robotId: string,
    position: [number, number, number],
    colorIndex: number,
    rotation?: number[],
    trackingStatus?: string,
    bodyYaw?: number,
    platformMetadata?: PlatformMetadata | null,
  ): void {
    const existing = this.markers.get(robotId);

    if (existing) {
      let marker = existing;
      const fallbackKey = this.fallbackMarkerKeys.get(robotId);
      const nextFallbackKey = this.getFallbackMarkerKey(platformMetadata);

      if (fallbackKey && fallbackKey !== nextFallbackKey) {
        this.removeMarker(robotId);
        this.createFallbackMarker(robotId, position, colorIndex, platformMetadata);
        marker = this.markers.get(robotId) ?? existing;
      }

      marker.position.set(position[0], position[1], position[2]);

      // Use MuJoCo body yaw directly for robot heading
      if (bodyYaw !== undefined) {
        marker.rotation.set(0, 0, bodyYaw);
      } else if (rotation && rotation.length === 9) {
        // Fallback: derive yaw from camera rotation matrix
        const lookX = -rotation[6];
        const lookY = -rotation[7];
        const yaw = Math.atan2(lookY, lookX) + Math.PI / 2;
        marker.rotation.set(0, 0, yaw);
      }

      // Tint robot marker by SLAM tracking status
      if (trackingStatus) {
        const statusColor = new THREE.Color(STATUS_COLORS[trackingStatus] ?? 0x00cc00);
        marker.traverse((child) => {
          if ((child as THREE.Mesh).isMesh) {
            const mat = (child as THREE.Mesh).material as THREE.MeshStandardMaterial;
            mat.color.copy(statusColor);
            mat.emissive.copy(statusColor);
          }
        });
      }
      return;
    }

    // Model still loading — queue the update
    if (!this.modelLoaded && !this.modelFailed) {
      this.pendingUpdates.set(robotId, { position, colorIndex, platformMetadata });
      return;
    }

    // Create new marker
    if (this.modelLoaded && this.templateModel) {
      this.createMeshMarker(robotId, position, colorIndex);
    } else {
      this.createFallbackMarker(robotId, position, colorIndex, platformMetadata);
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
      this.disposeMarkerObject(obj);
      this.scene.remove(obj);
    }
    this.markers.clear();
    this.fallbackMarkerKeys.clear();
    this.fallbackGeometry.dispose();
  }
}
