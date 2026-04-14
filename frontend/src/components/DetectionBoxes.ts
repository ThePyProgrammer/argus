import * as THREE from 'three';
import { OKABE_ITO_RGB } from '../utils/palette';
import type { Detection3DEnvelope } from '../utils/messageTypes';

/**
 * Renders 3D oriented bounding boxes (OBBs) with floating labels for
 * detected objects in the scene.
 *
 * Phase 2 (D-09 envelope): consumes Detection3DEnvelope from the backend.
 * Each item provides world-frame center + local-axis half_extents + quaternion.
 * MedianDepthLifter ships identity quaternion [0,0,0,1]; PointClusterLifter
 * (Phase 4 / DET-3D-01) will emit real OBB orientation.
 *
 * Each detection renders:
 * - Wireframe box sized from half_extents, rotated by quaternion
 * - Subtle translucent fill
 * - Text sprite label "class_name score%" above the box
 *
 * The optional 2D item.bbox_xyxy field is NOT consumed here; it is used by
 * CameraFeed.tsx for the RGB overlay (DET-UI-05). 3D rendering is OBB-only.
 */
export class DetectionBoxManager {
  private scene: THREE.Object3D;
  private boxes: Map<string, THREE.Group> = new Map(); // key = robotId
  private labelCanvas: HTMLCanvasElement;
  private labelCtx: CanvasRenderingContext2D;

  constructor(scene: THREE.Object3D) {
    this.scene = scene;
    // Shared canvas for text rendering
    this.labelCanvas = document.createElement('canvas');
    this.labelCanvas.width = 256;
    this.labelCanvas.height = 64;
    this.labelCtx = this.labelCanvas.getContext('2d')!;
  }

  /**
   * Update detection boxes for a robot using the Phase 2 detections_3d envelope.
   * @param robotId Robot identifier
   * @param envelope Detection3DEnvelope with OBB items (world-frame); null clears boxes
   * @param colorIndex Robot's palette index
   */
  updateDetections(
    robotId: string,
    envelope: Detection3DEnvelope | null,
    colorIndex: number,
  ): void {
    // Remove old boxes for this robot
    const existing = this.boxes.get(robotId);
    if (existing) {
      this.scene.remove(existing);
      existing.traverse((child) => {
        if ((child as THREE.Mesh).isMesh) {
          const mesh = child as THREE.Mesh;
          if (mesh.geometry) mesh.geometry.dispose();
          if (mesh.material) {
            const mat = mesh.material as THREE.Material;
            mat.dispose();
          }
        }
        if ((child as THREE.Sprite).isSprite) {
          const sprite = child as THREE.Sprite;
          (sprite.material as THREE.SpriteMaterial).map?.dispose();
          sprite.material.dispose();
        }
      });
    }

    const group = new THREE.Group();
    group.name = `detections-${robotId}`;

    const baseColor = OKABE_ITO_RGB[colorIndex % 8];
    const threeColor = new THREE.Color(
      baseColor[0] / 255,
      baseColor[1] / 255,
      baseColor[2] / 255,
    );

    // Short-circuit on null envelope (no detections): add empty group so the
    // clear-on-replace invariant holds.
    if (envelope === null) {
      this.scene.add(group);
      this.boxes.set(robotId, group);
      return;
    }

    for (const item of envelope.items) {
      const [cx, cy, cz] = item.center;
      const [hx, hy, hz] = item.half_extents;
      // Full box size = 2 * half_extents
      const boxGeo = new THREE.BoxGeometry(hx * 2, hy * 2, hz * 2);
      const boxMat = new THREE.MeshBasicMaterial({
        color: threeColor,
        wireframe: true,
        transparent: true,
        opacity: 0.7,
      });
      const box = new THREE.Mesh(boxGeo, boxMat);
      box.position.set(cx, cy, cz);
      // Phase 2: MedianDepthLifter ships identity quaternion [0,0,0,1].
      // Applying it is a no-op now but ready for Phase 4's PointClusterLifter real OBB orientation.
      const [qx, qy, qz, qw] = item.quaternion;
      box.quaternion.set(qx, qy, qz, qw);
      group.add(box);

      // Subtle solid fill
      const fillMat = new THREE.MeshBasicMaterial({
        color: threeColor,
        transparent: true,
        opacity: 0.15,
        side: THREE.DoubleSide,
      });
      const fill = new THREE.Mesh(boxGeo.clone(), fillMat);
      fill.position.set(cx, cy, cz);
      fill.quaternion.set(qx, qy, qz, qw);
      group.add(fill);

      // Text label sprite
      const label = this.createLabel(
        `${item.class_name} ${(item.score * 100).toFixed(0)}%`,
        threeColor,
      );
      label.position.set(cx, cy, cz + hz + 0.2); // above the box
      label.scale.set(1.0, 0.25, 1);
      group.add(label);
    }

    this.scene.add(group);
    this.boxes.set(robotId, group);
  }

  private createLabel(text: string, color: THREE.Color): THREE.Sprite {
    const canvas = this.labelCanvas;
    const ctx = this.labelCtx;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Background
    ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
    ctx.roundRect(2, 2, canvas.width - 4, canvas.height - 4, 8);
    ctx.fill();

    // Text
    ctx.font = 'bold 28px monospace';
    ctx.fillStyle = `rgb(${Math.round(color.r * 255)}, ${Math.round(color.g * 255)}, ${Math.round(color.b * 255)})`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(text, canvas.width / 2, canvas.height / 2);

    const texture = new THREE.CanvasTexture(canvas);
    texture.needsUpdate = true;

    const material = new THREE.SpriteMaterial({
      map: texture.clone(), // clone to avoid sharing
      transparent: true,
      depthWrite: false,
    });

    return new THREE.Sprite(material);
  }

  /** Remove all detection boxes. */
  clear(): void {
    for (const group of this.boxes.values()) {
      this.scene.remove(group);
    }
    this.boxes.clear();
  }

  dispose(): void {
    this.clear();
  }
}
