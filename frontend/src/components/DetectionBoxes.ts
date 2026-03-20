import * as THREE from 'three';
import { OKABE_ITO_RGB } from '../utils/palette';

/**
 * Renders 3D wireframe bounding boxes with floating labels for
 * detected objects in the scene. Based on DimOS's Boxes3D approach.
 *
 * Each detection gets:
 * - A wireframe box at the 3D position (sized by distance)
 * - A text sprite label showing class name + confidence
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
   * Update detection boxes for a robot.
   * @param robotId Robot identifier
   * @param detections Array of {class, confidence, pos_3d, depth}
   * @param colorIndex Robot's palette index
   */
  updateDetections(
    robotId: string,
    detections: Array<{
      class: string;
      confidence: number;
      pos_3d: number[] | null;
      depth?: number;
    }>,
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

    for (const det of detections) {
      if (!det.pos_3d || det.pos_3d.length < 3) continue;

      const [x, y, z] = det.pos_3d;
      const depth = det.depth ?? 3.0;
      const bbox = det.bbox ?? [0, 0, 100, 100];

      // Compute real-world box size from 2D bbox + depth + focal length
      // f = imgHeight / (2 * tan(fov/2)), fov=70°
      const imgH = 480; // MuJoCo render height
      const fovRad = (70 * Math.PI) / 180;
      const f = imgH / (2 * Math.tan(fovRad / 2));
      const bboxW = Math.abs(bbox[2] - bbox[0]);
      const bboxH = Math.abs(bbox[3] - bbox[1]);
      const worldW = Math.max(0.1, (bboxW * depth) / f);
      const worldH = Math.max(0.1, (bboxH * depth) / f);
      const worldD = Math.max(0.1, Math.min(worldW, worldH) * 0.5); // depth = half of smaller dimension

      // Wireframe box with real-world proportions
      const boxGeo = new THREE.BoxGeometry(worldW, worldD, worldH);
      const boxMat = new THREE.MeshBasicMaterial({
        color: threeColor,
        wireframe: true,
        transparent: true,
        opacity: 0.7,
      });
      const box = new THREE.Mesh(boxGeo, boxMat);
      box.position.set(x, y, z);
      group.add(box);

      // Solid face (subtle fill)
      const fillMat = new THREE.MeshBasicMaterial({
        color: threeColor,
        transparent: true,
        opacity: 0.15,
        side: THREE.DoubleSide,
      });
      const fill = new THREE.Mesh(boxGeo.clone(), fillMat);
      fill.position.set(x, y, z);
      group.add(fill);

      // Text label sprite
      const label = this.createLabel(
        `${det.class} ${(det.confidence * 100).toFixed(0)}%`,
        threeColor,
      );
      label.position.set(x, y, z + worldH * 0.6);
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
