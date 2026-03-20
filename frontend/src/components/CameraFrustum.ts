import * as THREE from 'three';
import { OKABE_ITO_RGB } from '../utils/palette';

/**
 * Renders camera frustum wireframes in the 3D scene showing where
 * each robot's camera is positioned and what direction it's looking.
 *
 * Each frustum shows:
 * - A small pyramid wireframe representing the camera FOV
 * - A line from the camera position along the look direction
 * - Color-coded per robot
 */
export class CameraFrustumManager {
  private scene: THREE.Object3D;
  private frustums: Map<string, THREE.Group> = new Map();

  constructor(scene: THREE.Object3D) {
    this.scene = scene;
  }

  /**
   * Update camera frustum for a robot.
   * @param robotId Robot identifier
   * @param position Camera world position [x, y, z]
   * @param rotation Flat 9-element 3x3 rotation matrix (row-major)
   * @param colorIndex Robot's palette index
   * @param fovDeg Vertical FOV in degrees
   * @param aspect Width/height aspect ratio
   */
  updateFrustum(
    robotId: string,
    position: [number, number, number],
    rotation: number[],
    colorIndex: number,
    fovDeg: number = 70,
    aspect: number = 640 / 480,
  ): void {
    // Remove old frustum
    const existing = this.frustums.get(robotId);
    if (existing) {
      this.scene.remove(existing);
      existing.traverse((child) => {
        if ((child as THREE.Mesh).isMesh || (child as THREE.Line).isLine) {
          const obj = child as THREE.Mesh | THREE.Line;
          obj.geometry?.dispose();
          if (obj.material) (obj.material as THREE.Material).dispose();
        }
      });
    }

    const group = new THREE.Group();
    group.name = `camera-frustum-${robotId}`;

    const baseRGB = OKABE_ITO_RGB[colorIndex % 8];
    const color = new THREE.Color(baseRGB[0] / 255, baseRGB[1] / 255, baseRGB[2] / 255);

    // Frustum dimensions
    const nearDist = 0.1;
    const farDist = 1.5; // show 1.5m of frustum
    const fovRad = (fovDeg * Math.PI) / 180;
    const nearH = nearDist * Math.tan(fovRad / 2);
    const nearW = nearH * aspect;
    const farH = farDist * Math.tan(fovRad / 2);
    const farW = farH * aspect;

    // Extract yaw from camera look direction (-Z of cam_xmat)
    // cam_xmat row 2 = Z-back axis. Camera looks along -Z.
    // Camera looks along body -Y. Robot forward is body +X = 90° CCW from -Y.
    const lookX = -rotation[6];
    const lookY = -rotation[7];
    const yaw = Math.atan2(lookY, lookX) + Math.PI / 2;

    // Build level camera axes from yaw (ignore pitch/roll from gait)
    const lookDir = new THREE.Vector3(Math.cos(yaw), Math.sin(yaw), 0);
    const camX = new THREE.Vector3(-Math.sin(yaw), Math.cos(yaw), 0);
    const camY = new THREE.Vector3(0, 0, 1);
    const camZ = lookDir.clone().negate(); // Z-back = opposite of look

    // Frustum corners in camera frame, then transform to world
    // Camera frame: X=right, Y=up, -Z=forward
    const corners = [
      // Near plane (4 corners) -- along -Z (actual camera look direction)
      { x: -nearW, y: -nearH, z: -nearDist },
      { x:  nearW, y: -nearH, z: -nearDist },
      { x:  nearW, y:  nearH, z: -nearDist },
      { x: -nearW, y:  nearH, z: -nearDist },
      // Far plane (4 corners)
      { x: -farW, y: -farH, z: -farDist },
      { x:  farW, y: -farH, z: -farDist },
      { x:  farW, y:  farH, z: -farDist },
      { x: -farW, y:  farH, z: -farDist },
    ];

    // Transform corners from camera frame to world frame
    const worldCorners = corners.map((c) => {
      const world = new THREE.Vector3(
        camX.x * c.x + camY.x * c.y + camZ.x * c.z + position[0],
        camX.y * c.x + camY.y * c.y + camZ.y * c.z + position[1],
        camX.z * c.x + camY.z * c.y + camZ.z * c.z + position[2],
      );
      return world;
    });

    // Draw frustum wireframe edges
    const edgeIndices = [
      // Near plane
      [0, 1], [1, 2], [2, 3], [3, 0],
      // Far plane
      [4, 5], [5, 6], [6, 7], [7, 4],
      // Connecting edges
      [0, 4], [1, 5], [2, 6], [3, 7],
    ];

    const lineGeo = new THREE.BufferGeometry();
    const linePositions: number[] = [];
    for (const [a, b] of edgeIndices) {
      linePositions.push(
        worldCorners[a].x, worldCorners[a].y, worldCorners[a].z,
        worldCorners[b].x, worldCorners[b].y, worldCorners[b].z,
      );
    }
    lineGeo.setAttribute('position', new THREE.Float32BufferAttribute(linePositions, 3));
    const lineMat = new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.6 });
    const lines = new THREE.LineSegments(lineGeo, lineMat);
    group.add(lines);

    // Draw look direction arrow (longer line from camera position)
    const arrowLength = 2.0;
    const arrowGeo = new THREE.BufferGeometry();
    const arrowEnd = new THREE.Vector3(
      position[0] + lookDir.x * arrowLength,
      position[1] + lookDir.y * arrowLength,
      position[2] + lookDir.z * arrowLength,
    );
    arrowGeo.setAttribute('position', new THREE.Float32BufferAttribute([
      position[0], position[1], position[2],
      arrowEnd.x, arrowEnd.y, arrowEnd.z,
    ], 3));
    const arrowMat = new THREE.LineBasicMaterial({ color, linewidth: 2 });
    const arrow = new THREE.Line(arrowGeo, arrowMat);
    group.add(arrow);

    // Small sphere at camera position
    const sphereGeo = new THREE.SphereGeometry(0.05, 8, 8);
    const sphereMat = new THREE.MeshBasicMaterial({ color });
    const sphere = new THREE.Mesh(sphereGeo, sphereMat);
    sphere.position.set(position[0], position[1], position[2]);
    group.add(sphere);

    this.scene.add(group);
    this.frustums.set(robotId, group);
  }

  dispose(): void {
    for (const group of this.frustums.values()) {
      this.scene.remove(group);
      group.traverse((child) => {
        if ((child as THREE.Mesh).isMesh || (child as THREE.Line).isLine) {
          const obj = child as THREE.Mesh | THREE.Line;
          obj.geometry?.dispose();
          if (obj.material) (obj.material as THREE.Material).dispose();
        }
      });
    }
    this.frustums.clear();
  }
}
