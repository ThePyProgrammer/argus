import * as THREE from 'three';
import { OKABE_ITO_RGB } from '../utils/palette';
import type { SemanticMapObject } from '../utils/messageTypes';

/**
 * Simple string hash for deterministic per-class color assignment.
 * Returns a non-negative integer.
 */
function hashString(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) {
    h = ((h << 5) - h + s.charCodeAt(i)) | 0;
  }
  return Math.abs(h);
}

/**
 * Imperative Three.js manager for semantic map wireframe OBBs with TTL-driven
 * opacity fade. Follows the DetectionBoxManager pattern (class with update/dispose
 * methods, managed by SceneViewer's useEffect).
 *
 * Phase 8 DET-STRETCH-03: ghosted wireframe boxes for the semantic map layer.
 * Visual distinction from DetectionBoxManager: wireframe-only (no solid fill),
 * per-class color (not per-robot), opacity fades with TTL.
 */
export class SemanticMapLayer {
  private scene: THREE.Object3D;
  private group: THREE.Group;
  private meshes: Map<string, THREE.Mesh> = new Map();

  constructor(scene: THREE.Object3D) {
    this.scene = scene;
    this.group = new THREE.Group();
    this.group.name = 'semantic-map';
    this.group.renderOrder = -1;
    this.scene.add(this.group);
  }

  /**
   * Add or update semantic map objects. Creates new meshes for unknown keys,
   * updates position/orientation/scale for existing ones.
   */
  updateObjects(objects: SemanticMapObject[]): void {
    const seen = new Set<string>();
    for (const obj of objects) {
      const key = String(obj.fused_track_id);
      seen.add(key);

      const [cx, cy, cz] = obj.center;
      const [hx, hy, hz] = obj.half_extents;
      const [qx, qy, qz, qw] = obj.quaternion;

      let mesh = this.meshes.get(key);
      if (!mesh) {
        // Per-class color from Okabe-Ito palette
        const colorIdx = hashString(obj.class_name) % 8;
        const rgb = OKABE_ITO_RGB[colorIdx];
        const color = new THREE.Color(rgb[0] / 255, rgb[1] / 255, rgb[2] / 255);

        const geometry = new THREE.BoxGeometry(1, 1, 1);
        const material = new THREE.MeshBasicMaterial({
          wireframe: true,
          transparent: true,
          depthWrite: false,
          color,
          opacity: 0.7,
        });
        mesh = new THREE.Mesh(geometry, material);
        this.group.add(mesh);
        this.meshes.set(key, mesh);
      }

      mesh.position.set(cx, cy, cz);
      mesh.quaternion.set(qx, qy, qz, qw);
      mesh.scale.set(hx * 2, hy * 2, hz * 2);
    }
  }

  /**
   * Remove semantic map objects by fused_track_id.
   */
  removeObjects(ids: number[]): void {
    for (const id of ids) {
      const key = String(id);
      const mesh = this.meshes.get(key);
      if (mesh) {
        this.group.remove(mesh);
        mesh.geometry.dispose();
        (mesh.material as THREE.Material).dispose();
        this.meshes.delete(key);
      }
    }
  }

  /**
   * Update opacity for a single object based on TTL fade.
   * Called per-frame from the animation loop for smooth fade.
   *
   * Opacity formula: 0.7 * clamp((ttl - age) / ttl, 0, 1)
   * where age = simTime - lastSeen
   */
  updateOpacityForObject(key: string, lastSeen: number, ttl: number, simTime: number): void {
    const mesh = this.meshes.get(key);
    if (!mesh) return;
    const age = simTime - lastSeen;
    const t = Math.max(0, Math.min(1, (ttl - age) / ttl));
    (mesh.material as THREE.MeshBasicMaterial).opacity = 0.7 * t;
  }

  /**
   * Toggle visibility of the entire semantic map layer.
   */
  setVisible(visible: boolean): void {
    this.group.visible = visible;
  }

  /**
   * Dispose all meshes and remove group from scene.
   */
  dispose(): void {
    for (const mesh of this.meshes.values()) {
      this.group.remove(mesh);
      mesh.geometry.dispose();
      (mesh.material as THREE.Material).dispose();
    }
    this.meshes.clear();
    this.scene.remove(this.group);
  }
}
